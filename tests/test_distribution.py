"""Distribution compatibility and verified platform-specific updates."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.updates import package_matches, update_asset, Updates
from backend.version import RELEASE_TAG
from tools.build_desktop import desktop_entry


class DistributionTests(unittest.TestCase):
    def test_windows_linux_and_mac_choose_their_own_package(self):
        names=['LumenStudio-0.5.2-R9-Windows-Setup.exe','LumenStudio-0.5.2-R9-Linux-amd64.deb','LumenStudio-0.5.2-R9-macOS-arm64.dmg','LumenStudio-0.5.2-R9-macOS-x86_64.dmg']
        for system,cpu,index in [('win32','AMD64',0),('linux','x86_64',1),('darwin','arm64',2),('darwin','x86_64',3)]:
            with self.subTest(system=system,cpu=cpu):
                self.assertEqual([package_matches(name,system,cpu) for name in names],[i==index for i in range(4)])
        self.assertFalse(package_matches(names[0],'linux','x86_64'))
        self.assertFalse(package_matches(names[2],'darwin','x86_64'))

    def test_update_service_selects_newest_release_for_this_platform(self):
        assets=[{'name':name,'size':100,'digest':'sha256:'+'a'*64,'browser_download_url':'https://github.com/Arizt00/LumenStudio/releases/download/v0.5.2-preview.9/'+name} for name in ['LumenStudio-0.5.2-R9-Windows-Setup.exe','LumenStudio-0.5.2-R9-Linux-amd64.deb','LumenStudio-0.5.2-R9-macOS-arm64.dmg']]
        release={'tag_name':'v0.5.2-preview.9','html_url':'https://github.com/Arizt00/LumenStudio/releases/tag/v0.5.2-preview.9','assets':assets}
        for system,cpu,suffix in [('win32','AMD64','.exe'),('linux','x86_64','.deb'),('darwin','arm64','.dmg')]:
            selected=update_asset([release],RELEASE_TAG,system,cpu)
            self.assertTrue(selected['name'].endswith(suffix))
        self.assertIsNone(update_asset([release],release['tag_name'],'linux','x86_64'))
        self.assertIsNone(update_asset([release],RELEASE_TAG,'darwin','x86_64'))

    def test_mac_and_linux_installer_verification_rejects_tampering(self):
        for system,cpu,name in [('linux','x86_64','LumenStudio-0.5.2-R9-Linux-amd64.deb'),('darwin','arm64','LumenStudio-0.5.2-R9-macOS-arm64.dmg')]:
            with tempfile.TemporaryDirectory() as temp,patch('backend.updates.sys.platform',system),patch('backend.updates.platform.machine',return_value=cpu):
                root=Path(temp);file=root/name;file.write_bytes(b'verified installer')
                downloads=type('Downloads',(),{'root':root})()
                updater=Updates(None,downloads)
                state={'status':'ready','transfer':{'path':str(file)},'available':{'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}}
                with patch.object(updater,'snapshot',return_value=state):
                    self.assertEqual(updater.installer(),file)
                    file.write_bytes(b'tampered')
                    with self.assertRaises(ValueError):updater.installer()

    def test_linux_menu_launches_the_installed_executable(self):
        entry=desktop_entry('/opt/lumen-studio/lumen','lumen-studio')
        self.assertIn('Exec="/opt/lumen-studio/lumen"',entry)
        self.assertIn('Terminal=false',entry)

if __name__=='__main__':unittest.main()
