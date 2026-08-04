/**
 * CHC Pro AI — OTPInput
 * 6-box OTP input with auto-advance, paste support, and backspace handling.
 * Design: IBM Plex Mono, navy #003F87, teal #0073CF border on focus.
 */
import { useRef, useState } from 'react';

export default function OTPInput({ length = 6, value = '', onChange, disabled = false }) {
  const inputs = useRef([]);
  const digits  = value.split('').slice(0, length);
  while (digits.length < length) digits.push('');

  function update(newDigits) {
    onChange(newDigits.join(''));
  }

  function handleChange(i, e) {
    const val = e.target.value.replace(/\D/g, '').slice(-1);
    const next = [...digits];
    next[i] = val;
    update(next);
    if (val && i < length - 1) inputs.current[i + 1]?.focus();
  }

  function handleKeyDown(i, e) {
    if (e.key === 'Backspace') {
      if (digits[i]) {
        const next = [...digits]; next[i] = ''; update(next);
      } else if (i > 0) {
        inputs.current[i - 1]?.focus();
      }
    }
    if (e.key === 'ArrowLeft'  && i > 0)           inputs.current[i - 1]?.focus();
    if (e.key === 'ArrowRight' && i < length - 1)  inputs.current[i + 1]?.focus();
  }

  function handlePaste(e) {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, length);
    const next   = pasted.split('').concat(Array(length).fill('')).slice(0, length);
    update(next);
    const focusIdx = Math.min(pasted.length, length - 1);
    inputs.current[focusIdx]?.focus();
  }

  const boxStyle = (i) => ({
    width: 48, height: 56,
    border: `1.5px solid ${digits[i] ? '#003F87' : '#CBD5E1'}`,
    borderRadius: 8,
    textAlign: 'center',
    fontSize: 22,
    fontFamily: "'IBM Plex Mono', monospace",
    fontWeight: 600,
    color: '#003F87',
    background: disabled ? '#F1F5F9' : '#FFFFFF',
    outline: 'none',
    caretColor: '#003F87',
    transition: 'border-color .15s',
    cursor: disabled ? 'not-allowed' : 'text',
  });

  return (
    <div
      style={{ display: 'flex', gap: 10 }}
      data-testid="otp-input-group"
    >
      {digits.map((d, i) => (
        <input
          key={i}
          ref={el => inputs.current[i] = el}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={d}
          disabled={disabled}
          style={boxStyle(i)}
          data-testid={`otp-digit-${i}`}
          onChange={e => handleChange(i, e)}
          onKeyDown={e => handleKeyDown(i, e)}
          onPaste={handlePaste}
          onFocus={e => e.target.select()}
        />
      ))}
    </div>
  );
}
