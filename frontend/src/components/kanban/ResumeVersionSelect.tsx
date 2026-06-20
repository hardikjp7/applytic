import { useResumes } from '../../hooks/useResumes'

interface Props {
  value: string
  onChange: (value: string) => void
  className?: string
  disabled?: boolean
}

/**
 * v2.2 Session 0 - resume version dropdown sourced from S3 uploads (via /resumes/list).
 * Replaces the old free-text resumeVersion input to strengthen traceability between
 * applications and actual uploaded resume files.
 *
 * Behavior:
 * - Loading: dropdown disabled with a "Loading resumes..." placeholder
 * - Empty (no resumes uploaded yet): disabled placeholder option + hint text below
 * - Stale value (app.resumeVersion set but not in the current S3 list - e.g. deleted
 *   from S3, or free-typed before this change): injected as a disabled, visually
 *   flagged option so the value is preserved and visible without being re-selectable
 *   as if it were a live resume.
 */
export default function ResumeVersionSelect({ value, onChange, className = '', disabled = false }: Props) {
  const { resumes, loading } = useResumes()

  const knownNames = new Set(resumes.map(r => r.versionName))
  const hasStaleValue = value.trim() !== '' && !knownNames.has(value)
  const noResumesUploaded = !loading && resumes.length === 0

  return (
    <div>
      <select
        className={className}
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled || loading || noResumesUploaded}
      >
        <option value="">{loading ? 'Loading resumes...' : noResumesUploaded ? 'No resumes uploaded yet' : 'Select a resume version'}</option>

        {hasStaleValue && (
          <option value={value} disabled>
            {value} (no longer in S3)
          </option>
        )}

        {resumes.map(r => (
          <option key={r.versionName} value={r.versionName}>
            {r.versionName}
          </option>
        ))}
      </select>

      {noResumesUploaded && (
        <p className="text-xs text-gray-400 mt-1">
          No resumes uploaded yet - head to the Resumes page to upload one first.
        </p>
      )}
    </div>
  )
}
