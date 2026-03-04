import sqlite3
conn = sqlite3.connect('instance/hopaoems_smoke_test.sqlite')
c = conn.cursor()
print(c.execute('SELECT sql FROM sqlite_master WHERE type=''table''').fetchall())
