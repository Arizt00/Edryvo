using UnityEngine;

namespace BlissTeam
{
    public sealed class CameraRig : MonoBehaviour
    {
        [SerializeField] private Transform target;
        [SerializeField] private float smoothness = 12f;
        private Vector3 offset;

        private void Start()
        {
            if (target != null) offset = transform.position - target.position;
        }

        private void LateUpdate()
        {
            if (target == null) return;
            float factor = 1f - Mathf.Exp(-smoothness * Time.deltaTime);
            transform.position = Vector3.Lerp(transform.position, target.position + offset, factor);
        }
    }
}
