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
      {/* Provenance (see apps/desktop/DESIGN.md "BrandMark provenance" for the
         full re-derive recipe): public/nadia-face-badge.jpg is a hand-derived
         head-and-shoulders, center-cropped, 256x256 JPEG re-encode of
         @nadicodeai/design-system's `./assets/nadia` export
         (src/assets/nadia.png, 1086x1448, sha256
         31bfe2d2615069924484b63785223c6b37d6c0b2e845192ead3cdb4fe6c574d8 as of
         design-system@0.2.0). Re-derive by hand whenever that source asset or
         DS version changes; this crop is not auto-generated from it. */}
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
