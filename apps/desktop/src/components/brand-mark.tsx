import { cn } from '@/lib/utils'

const assetPath = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`

// Brand mark: Nadia face crop with no decorative backing.
// Fills the tile (softly rounded); size via className (default size-14).
export function BrandMark({ className, ...props }: React.ComponentProps<'span'>) {
  return (
    <span
      className={cn(
        'inline-flex size-14 shrink-0 items-center justify-center overflow-hidden',
        className
      )}
      {...props}
    >
      <img
        alt="Nadia"
        className="size-full object-cover"
        height={256}
        src={assetPath('nadia-face-badge.jpg')}
        width={256}
      />
    </span>
  )
}
