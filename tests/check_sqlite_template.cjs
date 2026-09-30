// Usage: node tests/check_sqlite_template.cjs /path/to/application
// The application must have its real sqlite3 dependency installed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

async function main() {
  assert.ok(process.argv[2], 'Pass the template/application directory explicitly');
  const root = path.resolve(process.argv[2]);
  const databaseDir = path.join(root, 'backend/src/database');
  const init = require(path.join(databaseDir, 'init_db.js'));
  const { createTestDatabaseHarness } = require(path.join(databaseDir, 'test_harness.js'));
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'arc-sqlite-contract-'));
  const harness = createTestDatabaseHarness({
    dbPath: path.join(temporary, 'contract.sqlite'),
    seedDefault: true,
  });
  try {
    // Reproduces the benchmark failure: initialize, then seed via withTransaction.
    const runtime = await harness.setup();
    const handles = await Promise.all([
      init.initializeDatabase(), init.initializeDatabase(), init.initializeDatabase(),
    ]);
    assert.ok(handles[0]);
    assert.ok(handles.every(handle => handle === handles[0]));
    assert.equal(typeof handles[0].exec, 'function');

    await runtime.exec('CREATE TABLE contract_checks (id INTEGER PRIMARY KEY, value TEXT)');
    await runtime.withTransaction(async tx => {
      await tx.run('INSERT INTO contract_checks (value) VALUES (?)', ['committed']);
    });
    await assert.rejects(runtime.withTransaction(async tx => {
      await tx.run('INSERT INTO contract_checks (value) VALUES (?)', ['rolled back']);
      throw new Error('force rollback');
    }), /force rollback/);
    assert.deepEqual(await runtime.all('SELECT value FROM contract_checks'), [{ value: 'committed' }]);

    await init.closeDb();
    const reopened = await Promise.all([init.initializeDatabase(), init.initializeDatabase()]);
    assert.ok(reopened[0]);
    assert.equal(reopened[0], reopened[1]);
    assert.equal((await runtime.get('SELECT COUNT(*) AS count FROM contract_checks')).count, 1);
    await harness.reset();
    await runtime.exec('CREATE TABLE after_reset (id INTEGER PRIMARY KEY)');
    assert.deepEqual(await runtime.all('SELECT * FROM after_reset'), []);
    console.log('PASS: seeded harness, repeated/concurrent initialization, commit, rollback, reopen, reset');
  } finally {
    await harness.cleanup();
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
