# Auth-Gated App Testing Playbook (SurfAI)

## Step 1: Create Test User & Session
```bash
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test Surfer',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

## Step 2: Test Backend API
```bash
# Test auth endpoint
curl -X GET "$BACKEND_URL/api/auth/me" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"

# Test list analyses
curl -X GET "$BACKEND_URL/api/analyses" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

## Step 3: Browser Testing (when frontend testing on web)
The mobile app stores `session_token` in AsyncStorage and sends it via Authorization Bearer header.
For browser-based testing, use localStorage:
```javascript
await page.evaluate((token) => {
  window.localStorage.setItem('session_token', token);
}, 'YOUR_SESSION_TOKEN');
```

Notes:
- Mobile (Expo Go): session token saved to AsyncStorage
- Web preview: same – AsyncStorage maps to localStorage
- All authenticated API calls include `Authorization: Bearer <token>`

## Success Indicators
- /api/auth/me returns user object with user_id, email, name
- Dashboard loads list of past analyses
- Upload + analyse video succeeds
