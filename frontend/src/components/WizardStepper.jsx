/**
 * CHC Pro AI — WizardStepper
 * 5-step registration progress indicator.
 * Design: navy #003F87 active, green #059669 complete, gray #CBD5E1 pending.
 */
const STEPS = [
  { label: 'Basic info',    sub: 'Name & specialty' },
  { label: 'NPI verify',   sub: 'Provider identity' },
  { label: 'Verify email', sub: 'Security code' },
  { label: 'Password & 2FA', sub: 'Account security' },
  { label: 'Sign & submit', sub: 'Agreements' },
];

export default function WizardStepper({ currentStep }) {
  // currentStep is 1-indexed (1–5)
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '16px 24px', borderBottom: '1px solid #E2E8F0',
      background: '#FFFFFF', position: 'sticky', top: 0, zIndex: 10,
    }}
    data-testid="wizard-stepper"
    >
      {STEPS.map((step, idx) => {
        const num      = idx + 1;
        const done     = num < currentStep;
        const active   = num === currentStep;
        const pending  = num > currentStep;

        const circleColor = done ? '#059669' : active ? '#003F87' : '#CBD5E1';
        const textColor   = done ? '#059669' : active ? '#003F87' : '#94A3B8';
        const lineColor   = done ? '#059669' : '#E2E8F0';

        return (
          <div key={num} style={{ display: 'flex', alignItems: 'center' }}>
            {/* Step circle + labels */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 88 }}
                 data-testid={`wizard-step-${num}`}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%',
                background: circleColor,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13, fontWeight: 600, color: '#fff',
                transition: 'background .2s',
                boxShadow: active ? '0 0 0 4px #DBEAFE' : 'none',
              }}>
                {done ? '✓' : num}
              </div>
              <span style={{
                marginTop: 4, fontSize: 11, fontWeight: active ? 600 : 400,
                color: textColor, textAlign: 'center',
                fontFamily: "'IBM Plex Sans', sans-serif",
                lineHeight: 1.3,
              }}>
                {step.label}
              </span>
              <span style={{
                fontSize: 10, color: '#94A3B8',
                fontFamily: "'IBM Plex Sans', sans-serif",
              }}>
                {step.sub}
              </span>
            </div>

            {/* Connector line */}
            {idx < STEPS.length - 1 && (
              <div style={{
                width: 48, height: 2,
                background: lineColor,
                margin: '0 4px', marginBottom: 22,
                transition: 'background .2s',
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}
