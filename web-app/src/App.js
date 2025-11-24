import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';

// Welcome Page Component
const WelcomePage = () => {
  return (
    <div className="flex justify-center items-center min-h-screen bg-gray-50 p-8">
      <div className="text-center bg-white p-12 rounded-xl shadow-lg max-w-md w-full">
        <h1 className="text-4xl font-bold text-gray-800 mb-4">Welcome to PDF Processor</h1>
        <p className="text-gray-600 mb-8 text-lg">Upload and process your PDF files with ease.</p>
        <Link 
          to="/upload" 
          className="inline-block bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-lg transition-colors duration-300 font-medium"
        >
          Go to Upload Page
        </Link>
      </div>
    </div>
  );
};

// File Upload Page Component
const UploadPage = () => {
  const [selectedFile, setSelectedFile] = React.useState(null);
  const [uploading, setUploading] = React.useState(false);
  const [uploadStatus, setUploadStatus] = React.useState('');

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file && file.type === 'application/pdf') {
      setSelectedFile(file);
      setUploadStatus('');
    } else {
      setUploadStatus('Please select a valid PDF file.');
      setSelectedFile(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadStatus('Please select a PDF file first.');
      return;
    }

    setUploading(true);
    setUploadStatus('Uploading...');

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch('http://127.0.0.1:8000/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        setUploadStatus('File uploaded successfully!');
        setSelectedFile(null);
        // Reset file input
        document.getElementById('file-upload').value = '';
      } else {
        setUploadStatus('Upload failed. Please try again.');
      }
    } catch (error) {
      setUploadStatus('Error uploading file. Please check your connection.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="flex justify-center items-center min-h-screen bg-gray-50 p-8">
      <div className="text-center bg-white p-12 rounded-xl shadow-lg max-w-lg w-full">
        <h1 className="text-3xl font-bold text-gray-800 mb-8">Upload PDF File</h1>
        
        <div className="mb-8">
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            className="hidden"
            id="file-upload"
          />
          <label 
            htmlFor="file-upload" 
            className="inline-block bg-red-500 hover:bg-red-600 text-white px-6 py-3 rounded-lg cursor-pointer transition-colors duration-300 font-medium mb-4"
          >
            Choose PDF File
          </label>
          
          {selectedFile && (
            <div className="mt-4 p-4 bg-gray-100 rounded-lg text-left">
              <p className="text-gray-700 font-medium">Selected file: {selectedFile.name}</p>
              <p className="text-gray-600">Size: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className={`block w-full mt-4 px-6 py-3 rounded-lg font-medium transition-colors duration-300 ${
              !selectedFile || uploading
                ? 'bg-gray-400 cursor-not-allowed text-white'
                : 'bg-green-500 hover:bg-green-600 text-white'
            }`}
          >
            {uploading ? 'Uploading...' : 'Upload PDF'}
          </button>

          {uploadStatus && (
            <div className={`mt-4 p-3 rounded-lg font-medium ${
              uploadStatus.includes('success')
                ? 'bg-green-100 text-green-800 border border-green-300'
                : 'bg-red-100 text-red-800 border border-red-300'
            }`}>
              {uploadStatus}
            </div>
          )}
        </div>

        <Link 
          to="/" 
          className="inline-block bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-lg transition-colors duration-300 font-medium"
        >
          Back to Welcome
        </Link>
      </div>
    </div>
  );
};

// Navigation Component
const Navigation = () => {
  return (
    <nav className="bg-gray-800 p-4 shadow-md">
      <div className="container mx-auto">
        <Link 
          to="/" 
          className="text-white hover:text-blue-300 mr-8 font-medium transition-colors duration-300"
        >
          Home
        </Link>
        <Link 
          to="/upload" 
          className="text-white hover:text-blue-300 font-medium transition-colors duration-300"
        >
          Upload
        </Link>
      </div>
    </nav>
  );
};

// Main App Component
function App() {
  return (
    <Router>
      <div className="min-h-screen">
        <Navigation />
        <Routes>
          <Route path="/" element={<WelcomePage />} />
          <Route path="/upload" element={<UploadPage />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;