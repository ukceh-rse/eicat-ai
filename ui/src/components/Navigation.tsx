import { Link } from 'react-router'

export default function Navigation() {
    return (
        <nav className='sidebar-nav'>
            <div className="nav-header">
                <div className="nav-icon">
                    🤖
                </div>
                <h3 className="nav-title">EICAT-AI</h3>
            </div>
            <Link to="/" className="nav-link">Home</Link>
            <Link to="/extract" className="nav-link">Data Extraction</Link>
            <Link to="/upload" className="nav-link">Upload</Link>
        </nav>
    )
}