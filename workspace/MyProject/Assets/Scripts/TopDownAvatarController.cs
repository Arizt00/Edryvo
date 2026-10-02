using UnityEngine;

namespace BlissTeam
{
    /// <summary>
    /// Handles player movement and camera follow in a top-down view.
    /// </summary>
    public class TopDownAvatarController : MonoBehaviour
    {
        [Header("Movement")]
        [SerializeField] private float moveSpeed = 7.5f;
        [SerializeField] private Rigidbody rb;

        [Header("Camera")]
        [SerializeField] private Transform cameraTarget;
        [SerializeField] private float cameraFollowSpeed = 12f;
        [SerializeField] private Vector3 cameraOffset = new Vector3(0f, 10f, -10f);

        private Vector2 moveInput;
        private Camera mainCamera;

        private void Awake()
        {
            if (rb == null) rb = GetComponent<Rigidbody>();
            mainCamera = Camera.main;
            if (cameraTarget == null) cameraTarget = transform;
        }

        // Read input each frame
        private void Update()
        {
            moveInput = new Vector2(
                Input.GetAxisRaw("Horizontal"),
                Input.GetAxisRaw("Vertical")
            );
            moveInput = Vector2.ClampMagnitude(moveInput, 1f);
        }

        private void FixedUpdate()
        {
            if (rb == null) return;
            Vector3 movement = new Vector3(moveInput.x, 0f, moveInput.y);
            rb.MovePosition(rb.position + movement * moveSpeed * Time.fixedDeltaTime);
        }

        private void LateUpdate()
        {
            if (mainCamera == null || cameraTarget == null) return;
            Vector3 target = cameraTarget.position + cameraOffset;
            float blend = 1f - Mathf.Exp(-cameraFollowSpeed * Time.deltaTime);
            mainCamera.transform.position = Vector3.Lerp(mainCamera.transform.position, target, blend);
            mainCamera.transform.LookAt(cameraTarget);
        }
    }
}
