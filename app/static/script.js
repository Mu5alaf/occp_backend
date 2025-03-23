// Token storage in sessionStorage
let token = sessionStorage.getItem('token') || null;

// Check if already logged in on page load
window.onload = function() {
    if (token) {
        showMainContent();
    }
};

// Show main content after successful auth
function showMainContent() {
    document.getElementById('auth-section').classList.add('hidden');
    document.getElementById('chargers-section').classList.remove('hidden');
    document.getElementById('control-section').classList.remove('hidden');
    document.getElementById('transactions-section').classList.remove('hidden');
    document.getElementById('logout-section').classList.remove('hidden');
    startAutoRefresh();
}

// Hide main content and show auth section
function hideMainContent() {
    document.getElementById('auth-section').classList.remove('hidden');
    document.getElementById('chargers-section').classList.add('hidden');
    document.getElementById('control-section').classList.add('hidden');
    document.getElementById('transactions-section').classList.add('hidden');
    document.getElementById('logout-section').classList.add('hidden');
    stopAutoRefresh();
}

// Auto-refresh chargers list every 5 seconds
let refreshInterval = null;

function startAutoRefresh() {
    refreshInterval = setInterval(listChargers, 5000);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Register a new user
async function register() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const response = await fetch('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });
    const data = await response.json();
    if (response.ok) {
        token = data.access_token;
        sessionStorage.setItem('token', token);
        document.getElementById('auth-status').textContent = 'Registration successful! You are now logged in.';
        showMainContent();
    } else {
        document.getElementById('auth-status').textContent = 'Registration failed: ' + data.detail;
    }
}

// Login to get an authentication token
async function login() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const response = await fetch('/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `username=${username}&password=${password}`
    });
    const data = await response.json();
    if (response.ok) {
        token = data.access_token;
        sessionStorage.setItem('token', token);
        console.log("Token:", token);
        document.getElementById('auth-status').textContent = 'Login successful!';
        showMainContent();
    } else {
        document.getElementById('auth-status').textContent = 'Login failed: ' + data.detail;
    }
}

// Logout
function logout() {
    token = null;
    sessionStorage.removeItem('token');
    document.getElementById('auth-status').textContent = 'Logged out.';
    hideMainContent();
}

// Add a new charger
async function addCharger() {
    const chargerId = document.getElementById('new-charger-id').value;
    if (!chargerId) {
        document.getElementById('add-charger-status').textContent = 'Please enter a charger ID.';
        return;
    }
    const response = await fetch(`/add-charger?charger_id=${chargerId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
    });
    if (response.ok) {
        const data = await response.json();
        document.getElementById('add-charger-status').textContent = `Success: ${data.status} (${data.charger_id})`;
        listChargers();
    } else {
        const data = await response.json();
        document.getElementById('add-charger-status').textContent = `Failed: ${data.detail}`;
    }
}

// Fetch and display list of connected chargers
async function listChargers() {
    try {
        const data = await fetchWithAuth('/chargers');
        if (data) {
            updateChargersList(data.active_chargers);
        }
    } catch (error) {
        document.getElementById('auth-status').textContent = 'Failed to fetch chargers. Please log in again.';
        logout();
    }
}

// Start a charging session
async function startCharging() {
    const chargerId = document.getElementById('charger-id').value;
    if (!chargerId) {
        document.getElementById('control-status').textContent = 'Please enter a charger ID.';
        return;
    }
    try {
        const data = await fetchWithAuth(`/start/${chargerId}`, { method: 'POST' });
        document.getElementById('control-status').textContent = data.status || data.error;
    } catch (error) {
        document.getElementById('control-status').textContent = `Failed: ${error.message || 'Unknown error'}`;
        if (error.message.includes('401')) {
            document.getElementById('control-status').textContent = 'Session expired. Please log in again.';
            logout();
        }
    }
}

// Stop a charging session
async function stopCharging() {
    const chargerId = document.getElementById('charger-id').value;
    if (!chargerId) {
        document.getElementById('control-status').textContent = 'Please enter a charger ID.';
        return;
    }
    try {
        const data = await fetchWithAuth(`/stop/${chargerId}`, { method: 'POST' });
        document.getElementById('control-status').textContent = data.status || data.error;
    } catch (error) {
        document.getElementById('control-status').textContent = `Failed: ${error.message || 'Unknown error'}`;
        if (error.message.includes('401')) {
            document.getElementById('control-status').textContent = 'Session expired. Please log in again.';
            logout();
        }
    }
}

// Fetch and display list of transactions
async function listTransactions() {
    try {
        const data = await fetchWithAuth('/transactions');
        const list = document.getElementById('transactions-list');
        list.innerHTML = '';
        data.transactions.forEach(tx => {
            const li = document.createElement('li');
            li.textContent = `ID: ${tx.id}, Charger: ${tx.charger_id}, Start: ${tx.start_time}, End: ${tx.stop_time || 'In progress'}, Energy Consumed: ${tx.energy_consumed || 'N/A'} kWh`;
            list.appendChild(li);
        });
    } catch (error) {
        document.getElementById('auth-status').textContent = 'Failed to fetch transactions. Please log in again.';
        logout();
    }
}

// Helper function for authenticated fetch requests
async function fetchWithAuth(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            Authorization: `Bearer ${token}`
        }
    });
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`${response.status}: ${errorText}`);
    }
    return response.json();
}

// Update chargers list
function updateChargersList(chargers) {
    const list = document.getElementById('chargers-list');
    list.innerHTML = '';
    if (!chargers || !Array.isArray(chargers)) {
        list.innerHTML = '<li>No chargers found.</li>';
        return;
    }
    chargers.forEach(charger => {
        const li = document.createElement('li');
        if (typeof charger === 'object' && charger.id && charger.status && charger.last_seen) {
            const lastSeen = new Date(charger.last_seen).toLocaleString();
            li.textContent = `${charger.id} (Status: ${charger.status}, Last Seen: ${lastSeen})`;
        } else {
            li.textContent = 'Invalid charger data';
            console.error('Invalid charger object:', charger);
        }
        list.appendChild(li);
    });
}