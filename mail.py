from __future__ import print_function
import base64
import pickle
import os.path
import psycopg2
import json
from psycopg2 import sql
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime, timedelta

def googleAuthentication():
    print("[INFO][googleAuthentication] Authentication Initiated.")
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret.json', scopes=['https://www.googleapis.com/auth/gmail.modify'])
    credentials = flow.run_local_server(port=8080)
    if credentials:
        pickle.dump(credentials, open('token.pickle', 'wb'))
        service = build('gmail', 'v1', credentials=credentials)
        print("[INFO][googleAuthentication] Authentication successful.")
        return service
    else:
        print("[INFO][googleAuthentication] Authentication failed.")
        # return None
        exit(0)

def printPSQLData(dataArray):
    print('[INFO][printPSQLData] Started printing data')
    for data in dataArray:
        print(f"ID: {data['id']}")
        print(f"Subject: {data['Subject']}")
        print(f"Sender: {data['From']}")
        print(f"Label: {data['Label']}")
        print(f"Mark as read: {data['mark_as_read']}")
        print(f"Timestamp: {data['timestamp']}")
        print("=" * 30)
    print('[INFO][printPSQLData] Completed printing data')

def validateDB():
    try:
        connectionString = psycopg2.connect(database="myemail", user="postgres", password="Admin_athreyan")
        print("[INFO][validateDB] Connection to database established successfully !")
        return True
    except psycopg2.OperationalError as error:
        if "does not exist" in str(error):
            print("[INFO][validateDB] Database does not exist, creating it...")
            defaultConnectionString = psycopg2.connect(database="postgres", user="postgres", password="Admin_athreyan")
            defaultConnectionString.autocommit = True
            cur_default = defaultConnectionString.cursor()
            print("[INFO][validateDB] Default Connection Established")
            create_db_query = sql.SQL("CREATE DATABASE {}").format(sql.Identifier("myemail"))
            cur_default.execute(create_db_query)
            defaultConnectionString.commit()
            defaultConnectionString.close()
            print("[INFO][validateDB] Database 'myemail' created successfully !")
            connectionString = psycopg2.connect(database="myemail", user="postgres", password="Admin_athreyan")
            print("[INFO][validateDB] Connection to database established successfully !")
            return True
        else:
            print("[ERROR][validateDB] Failed to connect to database: ", error)
            raise
    finally:
        if connectionString:
            connectionString.close()

def validateTable():
    print("[INFO][validateTable] Function initiated for table validation")
    try:
        connectionString = psycopg2.connect(database="myemail", user="postgres", password="Admin_athreyan")
        connectionString.autocommit = True
        cursorObject = connectionString.cursor()
        cursorObject.execute("""CREATE TABLE IF NOT EXISTS mail_data (
            id SERIAL PRIMARY KEY,
            gmail_id TEXT UNIQUE NOT NULL,
            subject TEXT,
            sender TEXT,
            body TEXT,
            label TEXT,
            markAsRead TEXT,
            timestamp TIMESTAMP ); """) # label: Inbox, Important , markAsRead: true/ false
        print("[INFO][validateTable] Function completed for table validation")
        return True
    except Exception as tableValidationError:
        print("[ERROR][validateTable] Failed to validate table: ", tableValidationError)
        raise

def readAllEmailFromPSQL():
    try:
        print('[INFO][readEmailFromPSQL] Reading Emails From Local Database')
        connectionString = psycopg2.connect(database="myemail", user="postgres", password="Admin_athreyan")
        cursorObject = connectionString.cursor()
        cursorObject.execute("SELECT * FROM mail_data") 
        emails = cursorObject.fetchall()
        rules = loadRules('rule.json')
        for email in emails:
            id, gmail_id, subject, sender, body, label, mark_as_read, timestamp = email
            email_data = {'id': id, 'Subject': subject, 'Body': body, 'Label': label, 'From': sender, 'mark_as_read': mark_as_read, 'gmail_id': gmail_id, 'timestamp':timestamp}
            for rule in rules:
                evaluate_ruleResponse = evaluateRule(rule, email_data)
                if evaluate_ruleResponse:
                    performAction(rule, email_data)
                    printPSQLData([email_data])
    except psycopg2.Error as readAllEmailError:
        print('[INFO][readEmailFromPSQL] Error while reading All the email', readAllEmailError)
    finally:
        if connectionString:
            connectionString.close()

def readEmailsWithGAPI(service):
    try:
        subject = None; sender = None; body = None; timestamp_str = None; timestamp = None
        connectionString = psycopg2.connect(database="myemail", user="postgres", password="Admin_athreyan")
        cursorObject = connectionString.cursor();
        connectionString.autocommit = True
        mailObject = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=10).execute()
        messages = mailObject.get('messages', [])
        print("[INFO][readEmailsWithGAPI] Fetched mail objects")
        for message in messages:
            message_id = message['id']
            particularMail = service.users().messages().get(userId='me', id=message_id).execute()
            payload = particularMail['payload']
            headers = payload['headers']
            is_read = 'UNREAD' not in particularMail.get('labelIds', [])
            for header in headers:
                if header['name'] == 'Subject':
                    subject = header['value']
                elif header['name'] == 'From':
                    sender = header['value']
                elif header['name'] == 'Date':
                    timestamp_str = header['value'].rsplit(' ', 1)[0]
                if timestamp_str:
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%a, %d %b %Y %H:%M:%S")
                    except ValueError:
                        timestamp_str, _, timezone_str = timestamp_str.rpartition(' ')
                        offset = timedelta(hours=int(timezone_str[:3]), minutes=int(timezone_str[3:]))
                        timestamp = datetime.strptime(timestamp_str, "%a, %d %b %Y %H:%M:%S") + offset
                if 'body' in payload:
                    if 'data' in payload['body']:
                        body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                    elif 'attachmentId' in payload['body']:
                        attachment = service.users().messages().attachments().get(
                            userId='me', messageId=message_id, id=payload['body']['attachmentId']
                        ).execute()
                        body = base64.urlsafe_b64decode(attachment['data']).decode('utf-8')
            try:
                cursorObject.execute("""INSERT INTO mail_data (gmail_id, subject, sender, body, timestamp, label, markAsRead) VALUES (%s, %s, %s, %s, %s, %s, %s)""", (message_id, subject, sender, body, timestamp, 'INBOX', is_read))
            except psycopg2.IntegrityError as insertRecordError:
                if "duplicate key value violates unique constraint" in str(insertRecordError):
                    print(f"[INFO][readEmailsWithGAPI] Skipping duplicate entry for Gmail ID: {message_id}")
                else:
                    raise
        connectionString.commit()
        cursorObject.close()
        connectionString.close()
        return True
    except Exception as readGoogleAPIError:
        print("[ERROR][readEmailsWithGAPI] Failed to read Mail from Google: ", readGoogleAPIError)
        raise

def loadRules(file_path):
    with open(file_path, 'r') as file:
        print('[INFO][loadRules] Rule Json file read successfully !')
        return json.load(file)

def evaluateRule(rule, email):
    if rule['predicate'] == 'All':
        return all(evaluateCondition(condition, email) for condition in rule['conditions'])
    elif rule['predicate'] == 'Any':
        return any(evaluateCondition(condition, email) for condition in rule['conditions'])
    else:
        raise ValueError(f"Invalid predicate: {rule['predicate']}")

def evaluateCondition(condition, email):
    if condition['field'] != 'Received':
        field_value = email[condition['field']]
        if condition['predicate'] == 'Contains':
            return condition['value'] in field_value
        elif condition['predicate'] == 'Does not Contain':
            return condition['value'] not in field_value
        elif condition['predicate'] == 'Equals':
            return field_value == condition['value']
        elif condition['predicate'] == 'Does not equal':
            return field_value != condition['value']
        else:
            raise NotImplementedError("Date-based comparisons not yet implemented")
    else:
        return evaluateDateCondition(condition, email)

def evaluateDateCondition(condition, email):
    if condition['field'] == 'Received':
        field_value = email['timestamp']
        print('field_value', field_value)
        if isinstance(field_value, datetime):
            email_timestamp = field_value
        else:
            try:
                email_timestamp = datetime.strptime(field_value, '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                raise ValueError(f"Invalid timestamp format in email data: {field_value}")
        currentTime = datetime.now(datetime.utcnow().tzinfo)
        delta = currentTime - email_timestamp
        if condition['predicate'] == 'Less than days':
            return delta.days < int(condition['value'])
        elif condition['predicate'] == 'Greater than days':
            return delta.days > int(condition['value'])
        elif condition['predicate'] == 'Less than months':
            return (currentTime.year - email_timestamp.year) * 12 + currentTime.month - email_timestamp.month < int(condition['value'])
        elif condition['predicate'] == 'Greater than months':
            return (currentTime.year - email_timestamp.year) * 12 + currentTime.month - email_timestamp.month > int(condition['value'])
        else:
            raise NotImplementedError(f"Date predicate not implemented: {condition['predicate']}")

def performAction(rule, email):
    email_id = email['gmail_id']
    for action in rule['actions']:
        if action == 'Mark as read':
            googleService.users().messages().modify(userId='me', id=email_id, body={'removeLabelIds': ['UNREAD']}).execute()
        elif action == 'Mark as unread':
            googleService.users().messages().modify(userId='me', id=email_id, body={'addLabelIds': ['UNREAD']}).execute()
        elif action.startswith('Move Message:'):
            targetLabel = action.split(':')[1]
            label_id = None
            for label in listOfLabels:
                if str(label['name'].strip()) == str(targetLabel.strip()):
                    label_id = label.get('id')
                    break
            
            if label_id is None:
                print(f"Label '{targetLabel}' not found.")
                return
            try:
                googleService.users().messages().modify(userId='me', id=email_id, body={'addLabelIds': [label_id], 'removeLabelIds': ['INBOX']}).execute()
                print(f"[INFO][performAction]Email moved to '{targetLabel}' successfully.")
            except Exception as actionError:
                print(f"[ERROR][performAction]Error moving email: {str(actionError)}")
        else:
            raise ValueError(f"[ERROR][performAction]Invalid action: {action}")

def fetchLabels(service):
    try:
        response = service.users().labels().list(userId='me').execute()
        labels = response['labels']
        return labels
    except Exception as error:
        print('[ERROR][fetchLabels]Failed to fetch label details:', error)
        return None

if __name__ == '__main__':
    googleService = googleAuthentication();
    listOfLabels = fetchLabels(googleService);
    databaseExist = validateDB();
    if databaseExist:
        print("[INFO] Database connected Successfully")
        tableExist = validateTable();
        if tableExist:
            print("[INFO] Table validation Successfully")
            readGAPI = readEmailsWithGAPI(googleService);
            if readGAPI:
                print("[INFO] Latest 10 mails synced with PSQL")
                readAllEmailFromPSQL()
        else:
            print('[ERROR] Failed in table check')
    else:
        print('[ERROR] Failed in Database Check check')

