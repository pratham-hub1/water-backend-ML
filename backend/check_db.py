from sqlalchemy import create_engine, inspect

def check_database():
    """
    Check database connection and display table/column info.

    This function establishes a connection to the SQLite database, checks for the presence of the 'sensor_readings' table,
    and displays the columns in the table if it exists. If the table is not found, it prompts the user to run init_db.py.
    """
    try:
        # Establish a connection to the SQLite database
        engine = create_engine("sqlite:///./water_quality.db")
        inspector = inspect(engine)
        
        # Print a success message if the connection is established
        print("✅ Database connection successful!")
        
        # Print the tables in the database
        print("\n📋 Tables in the database:")
        print(inspector.get_table_names())
        
        # Check if the 'sensor_readings' table exists
        if 'sensor_readings' in inspector.get_table_names():
            # Print the columns in the 'sensor_readings' table
            print("\n📊 Columns in sensor_readings table:")
            for column in inspector.get_columns('sensor_readings'):
                print(f"- {column['name']} ({column['type']})")
        else:
            # Print an error message if the 'sensor_readings' table is not found
            print("\n❌ 'sensor_readings' table not found. Did you run init_db.py?")
            
    except Exception as e:
        # Print an error message if an exception occurs
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    # Call the check_database function if the script is run directly
    check_database()