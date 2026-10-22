'use strict';

const { X509Certificate, createHash } = require('node:crypto');
const roots = new Set(Object.values(require('./distrusted_roots.json')));
const keys = new Set(Object.values(require('./distrusted_keys.json')));

function derElement(der) {
  const count = der[1] & 0x80 ? der[1] & 0x7f : 0;
  if (count > 6) throw new Error('Unsupported public key size');
  const start = 2 + count;
  const length = count ? der.readUIntBE(2, count) : der[1];
  if (start + length > der.length) throw new Error('Invalid public key length');
  return { value: der.subarray(start, start + length), rest: der.subarray(start + length) };
}

function rsaModulus(key) {
  // KeyObject exports canonical DER, including for RSA-PSS keys without JWK export.
  const spki = derElement(key.export({ format: 'der', type: 'spki' })).value;
  const bits = derElement(derElement(spki).rest).value.subarray(1);
  const modulus = derElement(derElement(bits).value).value;
  if (!modulus.length || modulus[0] & 0x80) throw new Error('Non-canonical RSA public key');
  return BigInt('0x' + modulus.toString('hex')).toString(16);
}

function isDistrusted(pem) {
  const cert = new X509Certificate(pem);
  if (roots.has(cert.fingerprint256.replaceAll(':', '').toLowerCase())) return true;
  const key = cert.publicKey;
  if (!['rsa', 'rsa-pss', 'ec'].includes(key.asymmetricKeyType)) return false;
  const identity = key.asymmetricKeyType === 'ec'
    ? `ec:${Buffer.from(key.export({ format: 'jwk' }).x, 'base64url').toString('hex')}`
    : `rsa:${rsaModulus(key)}`;
  return keys.has(createHash('sha256').update(identity).digest('hex'));
}

function certificates(pem) {
  const certs = pem.match(/-----BEGIN CERTIFICATE-----[^]*?-----END CERTIFICATE-----/g);
  if (!certs?.length) throw new Error('Empty CA bundle');
  return certs;
}

module.exports = { isDistrusted, certificates };
