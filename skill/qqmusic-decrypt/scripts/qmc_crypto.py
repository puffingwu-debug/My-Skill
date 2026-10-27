# SPDX-License-Identifier: GPL-3.0-or-later
"""QMC2 primitives; see references/implementation.md for algorithm sources."""

import base64
import struct


def tea_block(block, key):
    a, b = struct.unpack('>II', block)
    k0, k1, k2, k3 = struct.unpack('>4I', key)
    total = 0xE3779B90
    for _ in range(16):
        b = (b - (((a << 4) + k2) ^ (a + total) ^ ((a >> 5) + k3))) & 0xFFFFFFFF
        a = (a - (((b << 4) + k0) ^ (b + total) ^ ((b >> 5) + k1))) & 0xFFFFFFFF
        total = (total - 0x9E3779B9) & 0xFFFFFFFF
    return struct.pack('>II', a, b)


def tea_decrypt(data, key):
    if len(data) < 16 or len(data) % 8:
        return None
    previous_plain = previous_cipher = bytes(8)
    plain = bytearray()
    for offset in range(0, len(data), 8):
        cipher = data[offset:offset + 8]
        block = tea_block(bytes(a ^ b for a, b in zip(cipher, previous_plain)), key)
        plain.extend(a ^ b for a, b in zip(block, previous_cipher))
        previous_plain, previous_cipher = block, cipher
    start = (plain[0] & 7) + 3
    if start + 7 > len(plain) or plain[-7:] != bytes(7):
        return None
    return bytes(plain[start:-7])


def parse_key(ekey):
    raw = base64.b64decode(ekey.strip('\0\r\n '), validate=True)
    prefix = b'QQMusic EncV2,Key:'
    if raw.startswith(prefix):
        first = tea_decrypt(raw[len(prefix):], b'386ZJY!@#*$%^&)(')
        second = tea_decrypt(first, b'**#!(#$%&^a1cZ,T') if first else None
        if not second:
            raise ValueError('EncV2 密钥解析失败')
        raw = base64.b64decode(second, validate=True)
    if len(raw) < 8:
        raise ValueError('密钥长度不足')
    simple = bytes.fromhex('695646382b20150b')
    tea_key = bytes(v for pair in zip(simple, raw[:8]) for v in pair)
    body = tea_decrypt(raw[8:], tea_key)
    return raw[:8] + body if body is not None else raw


def decrypt(data, key):
    out = bytearray(data)
    n = len(key)
    if n <= 300:
        for offset in range(len(out)):
            pos = offset % 0x7FFF if offset > 0x7FFF else offset
            index = (pos * pos + 71214) % n
            shift = (index + 4) & 7
            mask = ((key[index] << shift) & 255) | (key[index] >> shift)
            out[offset] ^= mask
        return out
    box = [i & 255 for i in range(n)]
    j = 0
    for i in range(n):
        j = (j + box[i] + key[i]) % n
        box[i], box[j] = box[j], box[i]
    hash_base = 1
    for value in key:
        if value:
            next_hash = hash_base * value
            if next_hash > 0xFFFFFFFF or next_hash <= hash_base:
                break
            hash_base = next_hash

    def segment_key(index):
        seed = key[index % n]
        return int(hash_base / ((index + 1) * seed) * 100.0) % n if seed else 0

    first = min(128, len(out))
    for pos in range(first):
        out[pos] ^= key[segment_key(pos)]
    pos = first
    while pos < len(out):
        end = min((pos // 5120 + 1) * 5120, len(out))
        skip = pos % 5120 + segment_key(pos // 5120)
        state, j, k = box.copy(), 0, 0
        for i in range(-skip, end - pos):
            j = (j + 1) % n
            k = (k + state[j]) % n
            state[j], state[k] = state[k], state[j]
            if i >= 0:
                out[pos + i] ^= state[(state[j] + state[k]) % n]
        pos = end
    return out
