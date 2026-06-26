import { useEffect } from 'react'

// Activates .land-reveal elements as they enter the viewport.
// Call once per page-level component. Safe to call multiple times -
// IntersectionObserver already-visible entries trigger immediately.
export function useScrollReveal() {
  useEffect(() => {
    const els = document.querySelectorAll('.land-reveal')
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(e => {
          if (e.isIntersecting) {
            e.target.classList.add('visible')
            observer.unobserve(e.target)
          }
        })
      },
      { threshold: 0.12 }
    )
    els.forEach(el => observer.observe(el))
    return () => observer.disconnect()
  }, [])
}
