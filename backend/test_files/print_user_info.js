const { db } = require('../config/db');
console.log(db.prepare("SELECT email, match_threshold, selected_companies FROM users WHERE email = 'mssurashe42@gmail.com'").get());
