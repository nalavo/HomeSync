# HomeSync Backend API

A Flask-based REST API for managing household chores with automated rotation and notifications.

## Features

- **Household Management**: Create and join households with unique codes
- **Chore Management**: Add, edit, delete, and assign chores
- **Automated Rotation**: Weekly, biweekly, monthly, or no rotation
- **Notifications**: Email and SMS reminders
- **Member Management**: Add/remove family members
- **Progress Tracking**: Track completion rates

## API Endpoints

### Household Management
- `POST /households` - Create new household
- `GET /households/<code>` - Get household details
- `POST /households/<code>/join` - Join household
- `DELETE /households/<code>` - Delete household

### Chore Management
- `GET /households/<code>/chores` - Get all chores
- `POST /households/<code>/chores` - Create new chore
- `PUT /chores/<id>` - Update chore
- `DELETE /chores/<id>` - Delete chore

### Member Management
- `GET /households/<code>/members` - Get all members
- `PUT /households/<code>/members/<name>/preferences` - Update preferences

### Notifications & Rotation
- `POST /households/<code>/rotate` - Manual rotation
- `GET /households/<code>/rotation-history` - Get rotation history
- `POST /households/<code>/notifications` - Send notification

## Environment Variables

- `DATABASE_URL` - PostgreSQL connection string (auto-provided by Railway)
- `SECRET_KEY` - Flask secret key
- `FLASK_DEBUG` - Debug mode (False for production)
- `PORT` - Port number (auto-provided by Railway)
- `CORS_ORIGINS` - Allowed CORS origins

## Deployment

This application is configured for Railway deployment with:
- Dockerfile for containerization
- Procfile for Gunicorn production server
- PostgreSQL database support
- Environment variable configuration

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SECRET_KEY="your-secret-key"
export FLASK_DEBUG=True

# Run the application
python app.py
```

## Production Features

- Gunicorn WSGI server
- PostgreSQL database
- Scheduled task runner for notifications
- Email/SMS notification support
- Automated chore rotation
