// Copyright (c) 2022 Alethea Katherine Flowers.
// Published under the standard MIT License.
// Full text available at: https://opensource.org/licenses/MIT

#include "potracelib.h"
#include <stddef.h>
#include <stdint.h>

/* Pulled from potrace/bitmap.h */
#define BM_WORDSIZE ((int)sizeof(potrace_word))
#define BM_WORDBITS (8 * BM_WORDSIZE)
#define BM_HIBIT (((potrace_word)1) << (BM_WORDBITS - 1))
#define BM_ALLBITS (~(potrace_word)0)
#define bm_scanline(bm, y) ((bm)->map + (ptrdiff_t)(y) * (ptrdiff_t)(bm)->dy)
#define bm_index(bm, x, y) (&bm_scanline(bm, y)[(x) / BM_WORDBITS])
#define bm_mask(x) (BM_HIBIT >> ((x) & (BM_WORDBITS - 1)))
#define bm_range(x, a) ((int)(x) >= 0 && (int)(x) < (a))
#define bm_safe(bm, x, y) (bm_range(x, (bm)->w) && bm_range(y, (bm)->h))
#define BM_UGET(bm, x, y) ((*bm_index(bm, x, y) & bm_mask(x)) != 0)
#define BM_USET(bm, x, y) (*bm_index(bm, x, y) |= bm_mask(x))
#define BM_UCLR(bm, x, y) (*bm_index(bm, x, y) &= ~bm_mask(x))
#define BM_UINV(bm, x, y) (*bm_index(bm, x, y) ^= bm_mask(x))
#define BM_UPUT(bm, x, y, b) ((b) ? BM_USET(bm, x, y) : BM_UCLR(bm, x, y))
#define BM_GET(bm, x, y) (bm_safe(bm, x, y) ? BM_UGET(bm, x, y) : 0)
#define BM_SET(bm, x, y) (bm_safe(bm, x, y) ? BM_USET(bm, x, y) : 0)
#define BM_CLR(bm, x, y) (bm_safe(bm, x, y) ? BM_UCLR(bm, x, y) : 0)
#define BM_INV(bm, x, y) (bm_safe(bm, x, y) ? BM_UINV(bm, x, y) : 0)
#define BM_PUT(bm, x, y, b) (bm_safe(bm, x, y) ? BM_UPUT(bm, x, y, b) : 0)

static inline size_t bitmap_getsize(int dy, size_t h) {
  size_t size;

  if (dy < 0) {
    dy = -dy;
  }

  size = (size_t)dy * (size_t)h * (size_t)BM_WORDSIZE;

  /* check for overflow error */
  if (size < 0 || (h != 0 && dy != 0 && size / h / dy != BM_WORDSIZE)) {
    return -1;
  }

  return size;
}

int potracecffi_pack_bitmap_data(potrace_bitmap_t *bm, uint8_t *data, size_t w,
                                 size_t h) {
  int dy = w == 0 ? 0 : (w - 1) / BM_WORDBITS + 1;
  size_t size = bitmap_getsize(dy, h);

  if (size <= 0) {
    return -1;
  }

  bm->map = (potrace_word *)calloc(1, size);

  if (bm->map == NULL) {
    return -1;
  }

  bm->w = w;
  bm->h = h;
  bm->dy = dy;

  for (size_t x = 0; x < w; x++) {
    for (size_t y = 0; y < h; y++) {
      BM_UPUT(bm, x, y, data[y * w + x]);
    }
  }

  return 0;
}

void potracecffi_free_bitmap_data(potrace_bitmap_t *bm) {
  if (bm->map == NULL) {
    return;
  }

  free(bm->map);
  bm->map = NULL;

  return;
}
