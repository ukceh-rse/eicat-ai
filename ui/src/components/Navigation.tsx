import { Link } from 'react-router'

export default function Navigation() {
    return (
        <nav className='sidebar-nav'>
            <div className="nav-header">
                <div className='mb-4'>
                    <a href="https://www.onestop-project.eu/" target="_blank" rel="noopener noreferrer" className="nav-header-link">
                        <div>
                            <img src="/onestop.svg" alt="EICAT-AI Logo" />
                        </div>
                        <div className="nav-title-image">
                            <img src="/onstop_title.svg" alt="EICAT-AI Title" />
                        </div>
                    </a>
                </div>
                <h3 className="nav-title">EICAT-AI</h3>
            </div>
            <Link to="/" className="nav-link">Home</Link>
            <Link to="/upload" className="nav-link">Upload</Link>
            <Link to="/analysis" className="nav-link">Analysis</Link>
        </nav>
    )
}