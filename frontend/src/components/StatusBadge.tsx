import clsx from 'clsx'

const STATUS_STYLES: Record<string, string> = {
  created:   'bg-gray-100 text-gray-600',
  ready:     'bg-blue-100 text-blue-700',
  detecting: 'bg-yellow-100 text-yellow-700 animate-pulse',
  running:   'bg-yellow-100 text-yellow-700 animate-pulse',
  pending:   'bg-gray-100 text-gray-500',
  done:      'bg-green-100 text-green-700',
  error:     'bg-red-100 text-red-700',
}

const STATUS_LABELS: Record<string, string> = {
  created:   'Created',
  ready:     'Ready',
  detecting: 'Detecting…',
  running:   'Running…',
  pending:   'Pending',
  done:      'Done',
  error:     'Error',
}

interface Props {
  status: string
  className?: string
}

export default function StatusBadge({ status, className }: Props) {
  return (
    <span
      className={clsx(
        'badge',
        STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600',
        className,
      )}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}
