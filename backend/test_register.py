import requests

res = requests.post("https://diamond-education.uz/api/auth/login", data={"username": "testuser_does_not_exist_xyz123", "password": "password"})
print("Login:", res.status_code, res.text)
if res.status_code == 401: # Try to register
    print("Need to register")
