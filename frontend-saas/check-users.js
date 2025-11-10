const { drizzle } = require('drizzle-orm/postgres-js');
const postgres = require('postgres');
require('dotenv').config();

const connectionString = process.env.POSTGRES_URL;
const client = postgres(connectionString);
const db = drizzle(client);

async function checkUsers() {
  try {
    console.log('Checking users table...\n');

    const result = await client`
      SELECT id, name, email, password_hash, role, created_at
      FROM users
      ORDER BY id DESC
      LIMIT 10
    `;

    console.log('Recent users:');
    console.log('='.repeat(80));
    result.forEach(user => {
      console.log(`ID: ${user.id}`);
      console.log(`Name: ${user.name}`);
      console.log(`Email: ${user.email}`);
      console.log(`Has Password: ${user.password_hash ? 'YES' : 'NO'}`);
      console.log(`Role: ${user.role}`);
      console.log(`Created: ${user.created_at}`);
      console.log('-'.repeat(80));
    });

    console.log(`\nTotal users found: ${result.length}`);

  } catch (error) {
    console.error('Error:', error);
  } finally {
    await client.end();
  }
}

checkUsers();
