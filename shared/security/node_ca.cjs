'use strict';

const fs = require('node:fs');
const tls = require('node:tls');
const { X509Certificate } = require('node:crypto');
const blocked = new Set(Object.values(require('./distrusted_roots.json')));
const pem = fs.readFileSync(process.env.CYXCBOT_CA_BUNDLE, 'utf8');
const certs = pem.match(/-----BEGIN CERTIFICATE-----[^]*?-----END CERTIFICATE-----/g);
if (!certs?.length || typeof tls.setDefaultCACertificates !== 'function') {
  throw new Error('Unsupported Node CA policy or empty CA bundle');
}
for (const pem of certs) {
  const fingerprint = new X509Certificate(pem).fingerprint256.replaceAll(':', '').toLowerCase();
  if (blocked.has(fingerprint)) throw new Error('Distrusted incident root in Node CA bundle');
}
tls.setDefaultCACertificates(certs);
