'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const tls = require('node:tls');
const { spawnSync } = require('node:child_process');
const { createRequire } = require('node:module');
const { certificates, isDistrusted } = require('../shared/security/node_ca_policy.cjs');

async function main() {
  const directory = path.dirname(process.execPath);
  let npm = [
    path.join(directory, 'node_modules/npm'),
    path.resolve(directory, '../lib/node_modules/npm'),
  ].find(candidate => fs.existsSync(path.join(candidate, 'bin/npm-cli.js')));
  if (!npm) {
    const entrypoint = path.join(directory, 'npm');
    if (fs.existsSync(entrypoint)) {
      const candidate = path.dirname(path.dirname(fs.realpathSync(entrypoint)));
      if (fs.existsSync(path.join(candidate, 'bin/npm-cli.js'))) npm = candidate;
    }
  }
  if (!npm) throw new Error('Cannot locate npm bundled with this Node runtime');
  if (typeof tls.getCACertificates !== 'function') throw new Error('Unsupported Node CA policy');
  const cli = fs.realpathSync(path.join(npm, 'bin/npm-cli.js'));
  const args = process.argv.slice(2);
  if (!args.length) throw new Error('Usage: secure_npm.cjs <npm command>');
  // Use npm's own configuration parser, including option aliases and project .npmrc.
  const npmRequire = createRequire(cli);
  const Config = npmRequire('@npmcli/config');
  const { definitions, shorthands, flatten } = npmRequire('@npmcli/config/lib/definitions');
  const envReplace = npmRequire('@npmcli/config/lib/env-replace');
  const config = new Config({ npmPath: npm, definitions, shorthands, flatten, env: { ...process.env }, argv: [process.execPath, cli, ...args] });
  await config.load();
  const cafile = config.get('cafile');
  if (cafile) certificates(fs.readFileSync(cafile, 'utf8'));
  const ca = config.flat.ca;
  let certs = ca == null ? tls.getCACertificates('default') : certificates([ca].flat().join('\n'));
  certs = certs.filter(cert => !isDistrusted(cert));
  if (!certs.length) throw new Error('No trusted certificates remain in the CA bundle');

  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'cyxcbot-npm-ca-'));
  try {
    const bundle = path.join(temporary, 'cacert.pem');
    fs.writeFileSync(bundle, certs.join('\n') + '\n');
    const preload = path.resolve(__dirname, '../shared/security/node_ca.cjs');
    const nodeOptions = [process.env.NODE_OPTIONS, config.get('node-options'), `--require ${JSON.stringify(preload)}`].filter(Boolean).join(' ');
    const protectedKeys = new Set(['ca', 'cafile', 'strict-ssl', 'node-options']);
    const env = { ...process.env };
    for (const key of Object.keys(env)) {
      if (/^npm_config_/i.test(key) && protectedKeys.has(key.slice(11).toLowerCase().replaceAll('_', '-'))) delete env[key];
    }
    Object.assign(env, {
      NODE_OPTIONS: nodeOptions,
      CYXCBOT_CA_BUNDLE: bundle,
      NODE_TLS_REJECT_UNAUTHORIZED: '1',
      npm_config_ca: 'null',
      npm_config_cafile: bundle,
      npm_config_strict_ssl: 'true',
      npm_config_node_options: nodeOptions,
    });
    // ca is an array: appending cafile cannot erase the original CLI trust.
    const options = Object.fromEntries(Object.entries(config.data.get('cli').raw)
      .filter(([key]) => key !== 'argv' && !protectedKeys.has(envReplace(key, process.env))));
    Object.assign(options, { cafile: bundle, 'strict-ssl': true, 'node-options': nodeOptions });
    const command = Object.entries(options).flatMap(([key, values]) => [values].flat()
      .map(value => `--${key}=${value instanceof Date ? value.toISOString() : value}`));
    command.push('--', ...config.parsedArgv.remain);
    const result = spawnSync(process.execPath, [cli, ...command], { env, stdio: 'inherit' });
    if (result.error) throw result.error;
    process.exitCode = result.status ?? 1;
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
