"""Dependency graph review and durable, all-or-nothing index installation."""
import io
import json
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from backend.extensions import ExtensionStore
from backend.preferences import Preferences,atomic_json


def package(name,deps=(),pack=(),version='1.0.0'):
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':name,'version':version,
            'license':'MIT','extensionDependencies':list(deps),'extensionPack':list(pack),
            'contributes':{'languages':[{'id':name,'extensions':['.'+name]}]}}))
        z.writestr('extension/payload.txt',name*100)
    return raw.getvalue()


class InstallPlanTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.prefs=Preferences(Path(self.temp.name));self.store=ExtensionStore(self.prefs)
        self.archives={'qa.shared':package('shared'),'qa.child':package('child',['qa.shared']),
            'qa.other':package('other',['qa.shared']),'qa.optional':package('optional')}
        self.requests=[]
    def tearDown(self):self.temp.cleanup()
    def remote(self,eid,version='latest',progress=lambda **kw:None,cancelled=lambda:False):
        self.requests.append(eid)
        if cancelled():raise InterruptedError('Revisión cancelada.')
        if eid not in self.archives:raise ValueError('Paquete no disponible: '+eid)
        return self.store.inspect_bytes(self.archives[eid],'Open VSX')
    def review(self,deps=('qa.child','qa.other'),packs=('qa.optional',)):
        return self.store.inspect_bytes(package('root',deps,packs))
    def prepare(self,root,include=False,**kwargs):
        with patch.object(self.store,'inspect_remote',side_effect=self.remote):
            return self.store.prepare_plan(root['ticket'],include,**kwargs)
    def test_required_graph_deduplicates_and_installs_in_dependency_order(self):
        root=self.review();plan=self.prepare(root)
        self.assertEqual([x['id'] for x in plan['packages']],['qa.shared','qa.child','qa.other','qa.root'])
        self.assertEqual(self.requests,['qa.child','qa.shared','qa.other']);self.assertEqual(self.store.list(),[])
        self.assertEqual(plan['size'],sum(x['size'] for x in plan['packages']))
        with self.assertRaises(PermissionError):self.store.install_plan(plan['plan'])
        result=self.store.install_plan(plan['plan'],True);self.assertEqual(len(result['installed']),4);self.assertEqual(self.store.pending,{})
        restored=ExtensionStore(self.prefs);self.assertEqual(set(restored.installed),{'qa.shared','qa.child','qa.other','qa.root'})
    def test_extension_pack_is_optional_and_its_required_dependencies_are_included(self):
        self.archives['qa.optional']=package('optional',['qa.shared'])
        plan=self.prepare(self.review(deps=()),True)
        self.assertEqual([x['id'] for x in plan['packages']],['qa.shared','qa.optional','qa.root'])
    def test_disabled_existing_dependency_is_retained_and_never_downloaded(self):
        old=self.store.install(self.store.inspect_bytes(self.archives['qa.shared'])['ticket'],True)
        self.store.update_state('qa.shared',False);plan=self.prepare(self.review(deps=['qa.child'],packs=[]))
        self.assertEqual(plan['existing'],[{'id':'qa.shared','version':'1.0.0','sha256':self.store.installed['qa.shared']['sha256'],'enabled':False}]);self.assertNotIn('qa.shared',self.requests)
        self.store.install_plan(plan['plan'],True);self.assertFalse(self.store.installed['qa.shared']['enabled'])
        self.assertEqual(old['directory'],self.store.installed['qa.shared']['directory'])
    def test_missing_dependency_cleans_children_but_keeps_parent_for_retry(self):
        root=self.review(deps=['qa.child','qa.missing'])
        with self.assertRaisesRegex(ValueError,'no disponible'):self.prepare(root)
        self.assertEqual(set(self.store.pending),{root['ticket']});self.assertEqual(self.store.list(),[])
    def test_installed_child_with_missing_grandchild_is_repaired_without_reinstall(self):
        child=self.store.install(self.store.inspect_bytes(self.archives['qa.child'])['ticket'],True)
        plan=self.prepare(self.review(deps=['qa.child'],packs=[]))
        self.assertEqual(self.requests,['qa.shared'])
        self.assertEqual([x['id'] for x in plan['packages']],['qa.shared','qa.root'])
        self.store.install_plan(plan['plan'],True)
        self.assertEqual(self.store.installed['qa.child']['directory'],child['directory'])
        self.assertIn('qa.shared',self.store.installed)
    def test_other_window_cannot_replace_reused_child_with_broken_dependency_graph(self):
        for version in ('2.0.0','1.0.0'):
            with self.subTest(replacementVersion=version):
                self.store.install(self.store.inspect_bytes(self.archives['qa.child'])['ticket'],True)
                plan=self.prepare(self.review(deps=['qa.child'],packs=[]))
                other=ExtensionStore(self.prefs);other.install(other.inspect_bytes(package('child',['qa.absent'],version=version))['ticket'],True)
                with self.assertRaisesRegex(ValueError,'cambió'):self.store.install_plan(plan['plan'],True)
                self.assertNotIn('qa.root',ExtensionStore(self.prefs).installed)
    def test_cycle_is_reported_and_all_children_are_discarded(self):
        self.archives['qa.child']=package('child',['qa.root']);root=self.review(deps=['qa.child'])
        with self.assertRaisesRegex(ValueError,'circulares'):self.prepare(root)
        self.assertEqual(set(self.store.pending),{root['ticket']})
    def test_cancel_after_child_review_cleans_children_and_never_installs(self):
        root=self.review(deps=['qa.child']);cancelled=[False]
        def remote(*args,**kwargs):
            result=self.remote(*args,**kwargs);cancelled[0]=True;return result
        with patch.object(self.store,'inspect_remote',side_effect=remote):
            with self.assertRaises(InterruptedError):self.store.prepare_plan(root['ticket'],cancelled=lambda:cancelled[0])
        self.assertEqual(set(self.store.pending),{root['ticket']});self.assertFalse(self.store.index.exists())
    def test_index_write_failure_rolls_back_payloads_and_can_retry_exact_plan(self):
        root=self.review();plan=self.prepare(root);original=dict(self.store.pending)
        def fail_index(path,data):
            if path==self.store.index:raise OSError('Disco de prueba lleno')
            atomic_json(path,data)
        with patch('backend.extension_install_plan.atomic_json',side_effect=fail_index):
            with self.assertRaisesRegex(OSError,'lleno'):self.store.install_plan(plan['plan'],True)
        self.assertEqual(self.store.list(),[])
        for ticket,(_,folder,_) in original.items():self.assertTrue(folder.is_dir());self.assertIn(ticket,self.store.pending)
        self.assertEqual(list(self.store.root.glob('*/.lumen-install.json')),[])
        self.store.install_plan(plan['plan'],True);self.assertEqual(len(self.store.list()),4)
    def test_other_window_install_is_reused_without_downgrade_or_enabling(self):
        plan=self.prepare(self.review());other=ExtensionStore(self.prefs)
        installed=other.install(other.inspect_bytes(package('shared',version='2.0.0'))['ticket'],True);other.update_state('qa.shared',False)
        result=self.store.install_plan(plan['plan'],True)
        self.assertIn('qa.shared',result['reused']);self.assertEqual(self.store.installed['qa.shared']['version'],'2.0.0')
        self.assertFalse(self.store.installed['qa.shared']['enabled']);self.assertEqual(installed['directory'],self.store.installed['qa.shared']['directory'])
    def test_expired_and_cancelled_plan_discards_all_review_folders(self):
        plan=self.prepare(self.review());self.store.plans[plan['plan']]['created']=time.monotonic()-601
        with self.assertRaisesRegex(ValueError,'caducado'):self.store.install_plan(plan['plan'],True)
        self.assertEqual(self.store.pending,{});self.assertEqual(self.store.plans,{})
    def test_completed_async_job_can_be_cancelled_without_leaking_plan(self):
        root=self.review()
        with patch.object(self.store,'inspect_remote',side_effect=self.remote):
            job=self.store.start_review({'ticket':root['ticket']});deadline=time.monotonic()+5
            while not (state:=self.store.review_status(job['id']))['done'] and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(state['done']);self.assertIn('plan',state['result'])
        self.store.review_status(job['id'],True);self.assertEqual(self.store.pending,{});self.assertEqual(self.store.plans,{})
    def test_concurrent_review_of_same_parent_is_rejected_before_download(self):
        root=self.review();entered=threading.Event();release=threading.Event();results=[]
        def remote(*args,**kwargs):entered.set();release.wait(5);return self.remote(*args,**kwargs)
        def prepare():results.append(self.store.prepare_plan(root['ticket']))
        with patch.object(self.store,'inspect_remote',side_effect=remote):
            thread=threading.Thread(target=prepare);thread.start();self.assertTrue(entered.wait(3))
            try:
                with self.assertRaisesRegex(ValueError,'pendiente'):self.store.prepare_plan(root['ticket'])
            finally:release.set();thread.join(5)
        self.assertEqual(len(results),1);self.assertEqual(len(self.store.plans),1)
    def test_package_limit_and_post_commit_audit_error_have_explicit_outcomes(self):
        root=self.review()
        with patch('backend.extension_install_plan.MAX_PLAN_PACKAGES',2):
            with self.assertRaisesRegex(ValueError,'32 paquetes'):self.prepare(root)
        self.assertEqual(set(self.store.pending),{root['ticket']});plan=self.prepare(root)
        with patch.object(self.prefs,'audit',side_effect=OSError('Auditoría no disponible')):result=self.store.install_plan(plan['plan'],True)
        self.assertEqual(len(result['installed']),4);self.assertEqual(len(result['warnings']),4)
        self.assertEqual(len(ExtensionStore(self.prefs).list()),4)

if __name__=='__main__':unittest.main()
