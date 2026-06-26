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

export default function Landing() {
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
