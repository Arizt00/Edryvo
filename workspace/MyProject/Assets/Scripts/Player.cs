using UnityEngine;

namespace BlissTeam
{
    public sealed class Player : MonoBehaviour
    {
        [SerializeField] private string displayName = "Aris";
        public string DisplayName => displayName;

        private void Start()
        {
            Debug.Log($"Welcome, {displayName}.");
        }
    }
}
