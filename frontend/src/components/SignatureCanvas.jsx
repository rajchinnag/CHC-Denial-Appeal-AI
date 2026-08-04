/**
 * CHC Pro AI — SignatureCanvas
 * HTML5 canvas signature pad. Exports base64 PNG.
 * Design: navy border, teal stroke color.
 */
import { useEffect, useRef, useState } from 'react';

export default function SignatureCanvas({ onChange, disabled = false }) {
  const canvasRef = useRef(null);
  const drawing   = useRef(false);
  const [isEmpty, setIsEmpty] = useState(true);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx    = canvas.getContext('2d');
    ctx.strokeStyle = '#003F87';
    ctx.lineWidth   = 2;
    ctx.lineCap     = 'round';
    ctx.lineJoin    = 'round';
  }, []);

  function getPos(e) {
    const rect = canvasRef.current.getBoundingClientRect();
    const src  = e.touches ? e.touches[0] : e;
    return { x: src.clientX - rect.left, y: src.clientY - rect.top };
  }

  function start(e) {
    if (disabled) return;
    e.preventDefault();
    drawing.current = true;
    const ctx = canvasRef.current.getContext('2d');
    const { x, y } = getPos(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
  }

  function move(e) {
    if (!drawing.current || disabled) return;
    e.preventDefault();
    const ctx = canvasRef.current.getContext('2d');
    const { x, y } = getPos(e);
    ctx.lineTo(x, y);
    ctx.stroke();
    setIsEmpty(false);
  }

  function end() {
    if (!drawing.current) return;
    drawing.current = false;
    if (!isEmpty) {
      onChange(canvasRef.current.toDataURL('image/png'));
    }
  }

  function clear() {
    const canvas = canvasRef.current;
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    setIsEmpty(true);
    onChange(null);
  }

  return (
    <div>
      <div style={{
        border: `1.5px solid ${isEmpty ? '#CBD5E1' : '#003F87'}`,
        borderRadius: 8, overflow: 'hidden', background: '#FAFAFA',
        cursor: disabled ? 'not-allowed' : 'crosshair',
        position: 'relative',
      }}>
        <canvas
          ref={canvasRef}
          width={560}
          height={180}
          style={{ display: 'block', width: '100%', touchAction: 'none' }}
          data-testid="signature-canvas"
          onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end}
          onTouchStart={start} onTouchMove={move} onTouchEnd={end}
        />
        {isEmpty && (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#94A3B8', fontSize: 14,
            fontFamily: "'IBM Plex Sans', sans-serif",
            pointerEvents: 'none',
          }}>
            Sign here using your mouse or touch
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={clear}
        disabled={isEmpty || disabled}
        data-testid="signature-clear-btn"
        style={{
          marginTop: 8, padding: '4px 12px', fontSize: 12,
          border: '1px solid #CBD5E1', borderRadius: 6,
          background: 'transparent', cursor: isEmpty ? 'not-allowed' : 'pointer',
          color: '#64748B', fontFamily: "'IBM Plex Sans', sans-serif",
        }}
      >
        Clear signature
      </button>
    </div>
  );
}
