import mysql.connector 

database = mysql.connector.connect(
    host='localhost',
    user='root',
    password='sevenzhiq',
    auth_plugin='mysql_native_password'
)

cursorObject = database.cursor()

cursorObject.execute("CREATE DATABASE pawmily_db")

print("Created successfully")
