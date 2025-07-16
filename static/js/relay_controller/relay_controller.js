// Relay Controller Plugin JavaScript

// Global variables for relay plugin
let relayToggling = false;

// Function to toggle relay state
async function toggleRelay(relayId) {
    if (relayToggling) return; // Prevent multiple simultaneous toggles
    
    relayToggling = true;
    
    try {
        const response = await fetch(`/api/plugins/relay_controller/toggle_relay/${relayId}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            updateRelayButtonState(relayId, data.state);
            showAlert(data.message, 'success');
        } else {
            showAlert(data.message || 'Failed to toggle relay', 'error');
        }
    } catch (error) {
        console.error('Relay toggle error:', error);
        showAlert('Network error - please try again', 'error');
    } finally {
        relayToggling = false;
    }
}

// Function to set specific relay state
async function setRelayState(relayId, state) {
    try {
        const stateParam = state ? 'on' : 'off';
        const response = await fetch(`/api/plugins/relay_controller/set_relay/${relayId}/${stateParam}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            updateRelayButtonState(relayId, data.state);
            return true;
        } else {
            console.error('Failed to set relay state:', data.message);
            return false;
        }
    } catch (error) {
        console.error('Set relay state error:', error);
        return false;
    }
}

// Function to update relay button visual state
function updateRelayButtonState(relayId, state) {
    // Update toolbar button if it exists
    const toolbarButton = document.querySelector(`[onclick="toggleRelay('${relayId}')"]`);
    if (toolbarButton) {
        // Update button class
        toolbarButton.className = toolbarButton.className
            .replace(/relay-(on|off)/g, '')
            .trim() + ` relay-${state ? 'on' : 'off'}`;
        
        // Update button color
        const icon = toolbarButton.querySelector('i');
        if (icon) {
            icon.style.color = state ? '#28a745' : '#c7c7c7';
        }
        
        // Update button background for active state
        toolbarButton.style.background = state ? '#2d5a31' : '#3a3a3a';
        toolbarButton.style.borderColor = state ? '#28a745' : '#555';
    }
}

// Function to refresh all relay states
async function refreshRelayStates() {
    try {
        const response = await fetch('/api/plugins/relay_controller/get_status');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update all relay button states
        for (const [relayId, relayInfo] of Object.entries(data)) {
            updateRelayButtonState(relayId, relayInfo.state);
        }
    } catch (error) {
        console.error('Relay status refresh error:', error);
    }
}

// Auto-refresh relay states every 10 seconds
setInterval(refreshRelayStates, 10000);

// Keyboard shortcuts for relays (Ctrl + 1-4)
document.addEventListener('keydown', function(event) {
    if (event.ctrlKey && event.key >= '1' && event.key <= '4') {
        event.preventDefault();
        const relayId = `relay_${event.key}`;
        toggleRelay(relayId);
    }
});

// Initialize relay states when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Refresh states after a short delay to ensure toolbar is loaded
    setTimeout(refreshRelayStates, 1000);
});

// Utility function to get relay status for external use
async function getRelayStatus() {
    try {
        const response = await fetch('/api/plugins/relay_controller/get_status');
        if (response.ok) {
            return await response.json();
        }
    } catch (error) {
        console.error('Error getting relay status:', error);
    }
    return null;
}

// Export functions for use by other parts of the application
window.relayController = { 
