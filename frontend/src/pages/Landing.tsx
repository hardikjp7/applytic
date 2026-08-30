import { useEffect, useRef } from 'react'
import { useNavigationType } from 'react-router-dom'
import '../components/landing/landing.css'
import Navbar from '../components/landing/Navbar'
import Hero from '../components/landing/Hero'
import LogoMarquee from '../components/landing/LogoMarquee'
import FeatureShowcase from '../components/landing/FeatureShowcase'
import HowItWorks from '../components/landing/HowItWorks'
import DeepDive from '../components/landing/DeepDive'   // v2.3 update
import About from '../components/landing/About'
import FAQ from '../components/landing/FAQ'
import CTABand from '../components/landing/CTABand'
import Footer from '../components/landing/Footer'

const SCROLL_KEY = 'applytic-landing-scroll'

export default function Landing() {
  // v3.1 fix: navigationType tells us whether this mount is a fresh visit
  // ('PUSH'/'REPLACE') or the result of the browser back button ('POP').
  // Only restore scroll on POP - a fresh visit to '/' should always start
  // at the top, even if a stale scroll value is still sitting in storage.
  const navigationType = useNavigationType()
  const hasRestoredRef = useRef(false)

  // v3.1 fix: persist scroll position continuously via a scroll listener
  // instead of snapshotting it in an effect-cleanup on unmount. Cleanup
  // timing is unreliable under React 18 StrictMode's dev-only double-invoke
  // behavior - it was firing before the restore's requestAnimationFrame had
  // actually applied the scroll, capturing scrollY=0 and clobbering the
  // saved position. A live listener has no such race.
  useEffect(() => {
    const onScroll = () => {
      sessionStorage.setItem(SCROLL_KEY, String(window.scrollY))
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    // Guard against StrictMode's double-invoke re-running this restore twice
    if (hasRestoredRef.current) return
    hasRestoredRef.current = true

    if (navigationType === 'POP') {
      const saved = sessionStorage.getItem(SCROLL_KEY)
      if (saved) {
        const target = parseInt(saved, 10)
        // Content (lazy-loaded chunks, scroll-reveal sections) may still be
        // laying out on first paint - retry across a few frames so the
        // scroll target reliably exists before we jump to it.
        let attempts = 0
        const tryScroll = () => {
          window.scrollTo({ top: target, behavior: 'auto' })
          attempts++
          if (attempts < 3) requestAnimationFrame(tryScroll)
        }
        requestAnimationFrame(tryScroll)
      }
    } else {
      window.scrollTo({ top: 0, behavior: 'auto' })
    }
  }, [navigationType])

  return (
    <div
      className="land-page land-noise relative"
      style={{
        background: '#0a0a0f',
        color: '#f9fafb',
        minHeight: '100vh',
        fontFamily: 'DM Sans, system-ui, sans-serif',
      }}
    >
      <Navbar />
      <Hero />
      <LogoMarquee />
      <FeatureShowcase />
      <HowItWorks />
      <DeepDive />
      <About />
      <FAQ />
      <CTABand />
      <Footer />
    </div>
  )
}