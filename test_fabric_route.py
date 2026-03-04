from src.hopaoems.app_factory import create_app

app = create_app()
client = app.test_client()

# Login first
response = client.post('/auth/login', data={
    'username': 'operator',
    'password': 'op123'
}, follow_redirects=False)

print(f"Login status: {response.status_code}")

# Now test fabric list
r = client.get('/fabric/', follow_redirects=False)
print(f"Fabric list status: {r. status_code}")
if r.status_code == 302:
    print(f"Redirecting to: {r.location}")
elif r.status_code == 200:
    print("✓ Fabric list page works!")
else:
    print(f"✗ Unexpected status: {r.status_code}")
