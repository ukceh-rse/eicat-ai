import { useState } from 'react';
import { Link } from 'react-router'

const MAX_FILE_SIZE_MB = 1;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const API_BASE_URL = 'http://localhost:8000';

interface UploadMetadata {
    id: string;
    filename: string;
    content_type: string;
    size: number;
    timestamp: string;
}

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
            <h1 className="text-3xl font-bold">Upload Data</h1>
            <p>Use the file browser below to select a PDF file for upload. The contents of the PDF will be converted to <a href="https://www.markdownguide.org/" target='_blank'>Markdown</a> format ready for analysis.</p>
            <p>You can view a list of all uploaded texts available for processing on the <Link to="/extract">Data Extraction</Link> page.</p>
            <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-xl font-semibold mb-4">Upload PDF Document</h2>

                <div className="space-y-4">
                    <input
                        type="file"
                        accept=".pdf"
                        onChange={handleFileSelect}
                        className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                    />

                    <p className="text-xs text-gray-500">Maximum file size: {MAX_FILE_SIZE_MB}MB</p>

                    {error && (
                        <div className="p-3 bg-red-50 border border-red-200 rounded">
                            <p className="text-sm text-red-600">{error}</p>
                        </div>
                    )}

                    {uploadResult && (
                        <div className="p-3 bg-green-50 border border-green-200 rounded">
                            <p className="text-sm text-green-600 font-medium">File uploaded successfully!</p>
                            <p className="text-xs text-green-600">ID: {uploadResult.id}</p>
                            <p className="text-xs text-green-600">Size: {(uploadResult.size / 1024 / 1024).toFixed(2)} MB</p>
                        </div>
                    )}

                    {file && !error && (
                        <>
                            <div className="p-3 bg-gray-50 rounded border">
                                <p className="text-sm font-medium">{file.name}</p>
                                <p className="text-xs text-gray-600">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                            </div>
                            <button
                                onClick={handleUpload}
                                disabled={uploading}
                                className={`w-full py-2 px-4 rounded ${
                                    uploading 
                                        ? 'bg-gray-400 text-gray-600 cursor-not-allowed' 
                                        : 'bg-blue-600 text-white hover:bg-blue-700'
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