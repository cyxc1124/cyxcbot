'use strict';

const fs = require('node:fs');
const tls = require('node:tls');
const { isDistrusted, certificates } = require('./node_ca_policy.cjs');
const pem = fs.readFileSync(process.env.CYXCBOT_CA_BUNDLE, 'utf8');
const certs = certificates(pem);
if (typeof tls.setDefaultCACertificates !== 'function') {
  throw new Error('Unsupported Node CA policy or empty CA bundle');
}
for (const pem of certs) {
  if (isDistrusted(pem)) throw new Error('Distrusted incident root in Node CA bundle');
}
tls.setDefaultCACertificates(certs);
