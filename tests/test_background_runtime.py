import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extension"


@unittest.skipUnless(shutil.which("node"), "Node.js is required for extension runtime tests")
class BackgroundRuntimeTests(unittest.TestCase):
    def test_run_command_message_routes_auth_and_exit_status(self):
        script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('extension/background.js', 'utf8');
let listener;
let storage = {token: 'test-token', activeProject: '/tmp/project'};
let request;
const chrome = {
  runtime: {onMessage: {addListener(fn) { listener = fn; }}},
  storage: {local: {async get() { return storage; }, async set() {}}},
};
const context = {
  chrome,
  URL,
  AbortController,
  setTimeout,
  clearTimeout,
  fetch: async (url, options) => {
    request = {url, options};
    return {ok: true, async json() { return {exitCode: 0, stdout: 'done', stderr: ''}; }};
  },
  console,
};
vm.runInNewContext(source, context);
function send(message) {
  return new Promise(resolve => {
    const keepAlive = listener(message, {}, resolve);
    if (keepAlive !== true) resolve(undefined);
  });
}
(async () => {
  const result = await send({type: 'VIBEBRIDGE_RUN_COMMAND', command: ['git', 'status']});
  if (!result.ok || result.exitCode !== 0 || result.stdout !== 'done') throw Error('successful command result was not preserved');
  if (request.url !== 'http://127.0.0.1:43127/run') throw Error('wrong endpoint');
  if (request.options.headers.Authorization !== 'Bearer test-token') throw Error('missing bearer token');
  const payload = JSON.parse(request.options.body);
  if (payload.project !== '/tmp/project' || payload.command[0] !== 'git') throw Error('wrong project/command payload');

  context.fetch = async () => ({ok: true, async json() { return {exitCode: 2, stdout: '', stderr: 'failed'}; }});
  const failed = await send({type: 'VIBEBRIDGE_RUN_COMMAND', command: ['git', 'status']});
  if (failed.ok !== false || failed.exitCode !== 2) throw Error('nonzero exit must be failure');

  storage = {activeProject: '/tmp/project'};
  const noToken = await send({type: 'VIBEBRIDGE_RUN_COMMAND', command: ['git', 'status']});
  if (!noToken.error || !noToken.error.includes('token missing')) throw Error('missing token not handled');

  storage = {token: 'test-token'};
  const noProject = await send({type: 'VIBEBRIDGE_RUN_COMMAND', command: ['git', 'status']});
  if (noProject.ok !== false || !noProject.error.includes('No active local project')) throw Error('missing project not handled');

  storage = {token: 'test-token', activeProject: '/tmp/project'};
  const invalid = await send({type: 'VIBEBRIDGE_RUN_COMMAND', command: 'git status'});
  if (invalid.ok !== false || !invalid.error.includes('Invalid command')) throw Error('invalid command not rejected');

  context.fetch = async () => ({ok: false, async json() { return {error: 'agent rejected request'}; }});
  const httpFailure = await send({type: 'VIBEBRIDGE_RUN_COMMAND', command: ['git', 'status']});
  if (httpFailure.ok !== false || !httpFailure.error.includes('agent rejected request')) throw Error('HTTP error not surfaced');

  let ignoredResponse = false;
  const ignored = listener({type: 'UNSUPPORTED_MESSAGE'}, {}, () => { ignoredResponse = true; });
  if (ignored !== undefined || ignoredResponse) throw Error('unsupported message should be ignored');
  process.stdout.write('background command bridge runtime tests PASS');
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            ["node", "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=10
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("runtime tests PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
