import { useState } from 'react';
import { Link } from 'react-router';
import type { UploadMetadata } from '../types';

const MAX_FILE_SIZE_MB = 3;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const API_BASE_URL = 'http://localhost:8000';

export default function Upload() {
    const [file, setFile] = useState<File | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [uploading, setUploading] = useState<boolean>(false);
    const [uploadResult, setUploadResult] = useState<UploadMetadata | null>(null);

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        setError(null);
        setUploadResult(null);

        if (selectedFile) {
            if (selectedFile.type !== 'application/pdf') {
                setError('Please select a PDF file.');
                return;
            }

            if (selectedFile.size > MAX_FILE_SIZE_BYTES) {
                setError(`File size must be less than ${MAX_FILE_SIZE_MB}MB.`);
                return;
            }

            setFile(selectedFile);
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        setUploading(true);
        setError(null);
        setUploadResult(null);

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(`${API_BASE_URL}/uploads/`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Upload failed: ${response.statusText}`);
            }

            const result: UploadMetadata = await response.json();
            setUploadResult(result);
            setFile(null);
            
            // Reset the file input
            const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
            if (fileInput) fileInput.value = '';
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Upload failed');
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className='card'>
            <h1 className="page-title">Upload Data</h1>
            <p>Use the file browser below to select a PDF file for upload. The contents of the PDF will be converted to <a href="https://www.markdownguide.org/" target='_blank'>Markdown</a> format ready for analysis.</p>
            <p>You can view a list of all uploaded texts available for processing on the <Link to="/analysis" className="link-primary">Analysis</Link> page.</p>
            <div className="upload-container">
                <h2 className="upload-title">Upload PDF Document</h2>

                <div className="upload-form">
                    <input
                        type="file"
                        accept=".pdf"
                        onChange={handleFileSelect}
                        className="file-input"
                    />

                    <p className="file-size-hint">Maximum file size: {MAX_FILE_SIZE_MB}MB</p>

                    {error && (
                        <div className="error-notification">
                            <p className="error-text">{error}</p>
                        </div>
                    )}

                    {uploadResult && (
                        <div className="success-notification">
                            <p className="success-text">File uploaded successfully!</p>
                            <p className="success-detail">ID: {uploadResult.id}</p>
                            <p className="success-detail">Size: {(uploadResult.size / 1024 / 1024).toFixed(2)} MB</p>
                        </div>
                    )}

                    {file && !error && (
                        <>
                            <div className="file-preview">
                                <p className="file-name">{file.name}</p>
                                <p className="file-size">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                            </div>
                            <button
                                onClick={handleUpload}
                                disabled={uploading}
                                className={`button-upload ${
                                    uploading 
                                        ? 'button-upload-disabled' 
                                        : 'button-upload-enabled'
                                }`}
                            >
                                {uploading ? 'Uploading...' : 'Upload'}
                            </button>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}