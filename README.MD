This starts both the FastAPI server (on port 8000) and the WebSocket server (on port 9000).

7. **Access the Frontend**:
Open your browser to `http://localhost:8000/static/index.html` to use the interface.

## Usage

### 1. Register and Log In
- Use the frontend’s "Register" form to create an account, then log in to get an access token.
- The token is stored in `sessionStorage` for authenticated requests.

### 2. Manage Chargers
- **Add a Charger**: Enter a unique charger ID in the "Add Charger" section and submit.
- **List Chargers**: The charger list updates every 5 seconds, showing connected chargers.

### 3. Control Charging
- **Start Charging**: Enter a charger ID and click "Start Charging" to begin a session.
- **Stop Charging**: Use the same ID to stop an ongoing session.
- If a charger is connected via WebSocket, commands are sent via OCPP; otherwise, actions are simulated in the database.

### 4. View Transactions
- Click "Refresh Transactions" to see a list of all charging sessions, including start times and charger IDs.

### API Endpoints
The backend provides a RESTful API (viewable at `http://localhost:8000/docs`):
- `POST /auth/register`: Create a new user.
- `POST /auth/token`: Log in and get a token.
- `POST /add-charger`: Add a charger by ID.
- `GET /chargers`: List all chargers.
- `POST /start/{charger_id}`: Start a charging session.
- `POST /stop/{charger_id}`: Stop a charging session.
- `GET /transactions`: Get transaction history.

## Project Structure

- `app/main.py`: Core application with FastAPI and WebSocket setup.
- `app/models.py`: SQLAlchemy models for chargers, transactions, and users.
- `app/auth.py`: Authentication logic (JWT, password hashing).
- `app/database.py`: Database configuration.
- `static/index.html`: Frontend interface (served by FastAPI).

## Contributing

We’d love your help! To contribute:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature-name`).
3. Commit your changes (`git commit -m "Add feature"`).
4. Push to your branch (`git push origin feature-name`).
5. Open a Pull Request.

Report bugs or suggest features via the Issues tab.

## Troubleshooting

- **Database Errors**: Ensure your `DATABASE_URL` is correct and PostgreSQL is running.
- **WebSocket Issues**: Verify port 9000 is open and not blocked by a firewall.
- **Frontend Not Loading**: Check that the `static` directory exists and contains `index.html`.

