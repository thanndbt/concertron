import sqlite3
from datetime import datetime, timedelta
from logmanager import LogManager

logger = LogManager(__name__)

class DatabaseManager:
    def __init__(self, db_name):
        self.db_name = db_name
        self.connection = None
        self.cursor = None
        self.connect()

    def connect(self):
        try:
            self.connection = sqlite3.connect(self.db_name)
            self.cursor = self.connection.cursor()
            logger.info(f'Successfully connected to database {self.db_name}')
        except sqlite3.Error as e:
            logger.error(f'Error connecting to database: {e}')

    def disconnect(self):
        if self.connection:
            self.connection.close()
            logger.info('Disconnected from database')

    def execute_query(self, query, params=None):
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            self.connection.commit()
            print("Query executed successfully")
        except sqlite3.Error as e:
            print(f"Error executing query: {e}")

    async def retrieve_event(self, event_id): # retrieves an event from database by id, returns None if none exist
        try:
            logger.debug(f'{event_id}: Checking and retrieving event')
            self.cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = self.cursor.fetchone()
            if row:
                logger.debug(f'{event_id}: Event exists')
                columns = [description[0] for description in self.cursor.description]
                return dict(zip(columns, row)) # Using dicts for ease of use and consistency throughout script, default from db is tuple
            else:
                logger.debug(f'{event_id}: Event does not exist')
                return None
        except Exception as e:
            logger.exception(f"Error retrieving {event_id} from db: {e}")
            print(f"Error retrieving event from db: {e}")

    async def should_recheck_event(self, event_id): # checks last_check and returns a value depending on timedelta to see if an individual event page should be checked again. if retrieve_event returns None, event does not exist, and function passes this on
        try:
            event = await self.retrieve_event(event_id)
            if event:
                time_diff = datetime.now() - datetime.fromisoformat(event.get('last_check'))
                if time_diff > timedelta(days=3):
                    return "EVENT_UPDATE"
                else:
                    return "EVENT_EXISTS"
            else:
                return "EVENT_DOES_NOT_EXIST"

        except Exception as e:
            logger.exception(f"Error checking whether recheck is needed: {e}")
            # logger.exception(traceback.print_exc(limit=1))
            print(f"Error checking whether recheck is needed: {e}")

    async def insert_event_data(self, data): # Inserts a new event into the database. Data is generate by the parse function of respective venues.
        try:
            self.cursor.execute("Insert INTO events (id, artist, subtitle, support, date, location, tags, ticket_status, url, venue_id, last_check, last_modified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (data['id'], data['artist'], data['subtitle'], data['support'], data['date'], data['location'], data['tags'], data['ticket_status'], data['url'], data['venue_id'], data['last_check'], data['last_modified']))
            self.connection.commit()
        except Exception as e:
            logger.exception(f"Error inserting event into database: {e}")
            print(f"Error inserting event into database: {e}")

    async def update_event_data(self, event_id, data): # updates an existing event entry by id
        try:
            stored_event = await self.retrieve_event(event_id) # retrieves the existing event from the db
            if stored_event: # This should not be necessary, but better safe than sorry
                changes = {key: value for key, value in data.items() if stored_event[key] != value} # Checks differences between the existing event and the newly scraped data and puts them in a dict

                if changes: # if changes is not an empty dict
                    # Construct the UPDATE query
                    logger.debug('Changes to ' + str(event_id) + ': ' + str(changes))
                    changes['last_check'] = datetime.now()
                    changes['last_modified'] = datetime.now()
                    set_clause = ', '.join(f"{key} = ?" for key in changes.keys())
                    query = f"UPDATE events SET {set_clause} WHERE id = ?"
                    values = tuple(changes.values()) + (event_id,)

                    # Execute the UPDATE query
                    self.cursor.execute(query, values)
                    self.connection.commit()
                else: # Only update last_check if no changes are made to actual event data
                    logger.debug(f'No changes to {event_id}')
                    self.cursor.execute("UPDATE events SET last_check=? WHERE id=?", (datetime.now(), event_id))
            else:
                raise Exception('stored_event is empty or wrong dtype: ' + str(type(stored_event)))
        except Exception as e:
            logger.exception(f'Failed to update event entry in db: {e}')


