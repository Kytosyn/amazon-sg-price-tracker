/**
 * Outbound affiliate linking for DiskPrices SG.
 * Amazon.sg Associates: append tag= when VITE_AMAZON_ASSOCIATE_TAG is set.
 * Shopee/Lazada click links: pass-through for now (ingest APIs remain parked).
 */

const AMAZON_TAG = String(import.meta.env.VITE_AMAZON_ASSOCIATE_TAG || '').trim()

export function hasAmazonAssociateTag() {
  return AMAZON_TAG.length > 0
}

function isAmazonUrl(url, platform) {
  if (platform === 'Amazon.sg') return true
  if (!url) return false
  try {
    const host = new URL(url).hostname.toLowerCase()
    return host === 'amazon.sg' || host.endsWith('.amazon.sg') || host === 'www.amazon.sg'
  } catch {
    return /amazon\.sg/i.test(url)
  }
}

/** Rewrite a product URL for affiliate attribution when configured. */
export function affiliateUrl(url, platform) {
  if (!url || !hasAmazonAssociateTag() || !isAmazonUrl(url, platform)) {
    return url
  }
  try {
    const u = new URL(url)
    u.searchParams.set('tag', AMAZON_TAG)
    return u.toString()
  } catch {
    return url
  }
}

/** rel attribute: include sponsored when the link carries our Associates tag. */
export function affiliateRel(url, platform) {
  const href = affiliateUrl(url, platform)
  let tagged = false
  if (hasAmazonAssociateTag() && isAmazonUrl(url, platform)) {
    try {
      tagged = new URL(href).searchParams.get('tag') === AMAZON_TAG
    } catch {
      tagged = false
    }
  }
  return tagged ? 'noopener noreferrer sponsored' : 'noopener noreferrer'
}
