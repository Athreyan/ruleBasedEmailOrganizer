
# Email Organizer

This Python script automates email organization tasks by integrating with the Gmail API and PostgreSQL database. It fetches emails from Gmail, stores them in a PostgreSQL database, and applies user-defined rules to perform actions such as marking emails as read, moving them to specific labels, or filtering based on conditions.

## Features

- **Authentication with Gmail API:** Connects to Gmail using OAuth2 authentication and retrieves emails from the user's inbox.
- **Database interaction with PostgreSQL:** Stores email data in a PostgreSQL database, ensuring persistence and queryability.
- **Rule-based actions:** Applies customizable rules defined in a JSON file to perform actions on emails based on specific criteria.
- **Logging and error handling:** Provides informative logs for tracking script execution and error messages for debugging.

## Usage

1. **Install dependencies:**
   ```bash
   pip install psycopg2 google-api-python-client google-auth-oauthlib google-auth-httplib2
   ```
2. **Create a client_secret.json file:** Obtain OAuth2 credentials from the Google API Console and save them in a file named `client_secret.json` in the same directory as the script. Ensure Authorized redirect URIs are listed in Google console.
3. **Run the script:**
   ```bash
   python main.py
   ```

## Configuration

- **rule.json:** This file contains a list of rules to apply to emails. Each rule specifies conditions and actions to take.
- **client_secret.json:** This file contains your Google API credentials for authentication.

## Functions

- **googleAuthentication():** Handles OAuth2 authentication with Gmail API.
- **validateDB():** Verifies database connection and creates the database if it doesn't exist.
- **validateTable():** Ensures the existence of the required table in the database.
- **readEmailsWithGAPI():** Fetches emails from Gmail and stores them in the database.
- **loadRules():** Loads rules from the JSON file.
- **evaluateRule():** Evaluates a rule against an email.
- **evaluateCondition():** Evaluates a single condition within a rule.
- **evaluateDateCondition():** Evaluates conditions based on email timestamps.
- **performAction():** Executes actions specified in a rule.
- **fetchLabels():** Fetches available Gmail labels.

## Additional Information

- The script currently fetches only the 10 latest emails from the inbox.
- The `markAsRead` action in rules only affects the local database label, not the Gmail label.
- Date-based comparisons are not yet implemented for all predicates.
