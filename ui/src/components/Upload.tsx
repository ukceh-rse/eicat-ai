import { useState } from 'react';

export default function Upload() {
    const [file, setFile] = useState<File | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        setError(null);

        if (selectedFile) {
            if (selectedFile.type !== 'application/pdf') {
                setError('Please select a PDF file.');
                return;
            }

            if (selectedFile.size > 1 * 1024 * 1024) { // 5MB in bytes
                setError('File size must be less than 1MB.');
                return;
            }

            setFile(selectedFile);
        }
    };

    const handleUpload = () => {
        if (file) {
            console.log('Uploading file:', file.name);
            // Handle upload logic here
        }
    };

    return (
        <div className='card'>
            <h1 className="text-3xl font-bold">Upload Data</h1>
            <p>Use the file browser below to select a PDF file for upload. The contents of the PDF will be converted to <a href="https://www.markdownguide.org/" target='_blank'>Markdown</a> format ready for analysis.</p>
            <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-xl font-semibold mb-4">Upload PDF Document</h2>

                <div className="space-y-4">
                    <input
                        type="file"
                        accept=".pdf"
                        onChange={handleFileSelect}
                        className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                    />

                    <p className="text-xs text-gray-500">Maximum file size: 1MB</p>

                    {error && (
                        <div className="p-3 bg-red-50 border border-red-200 rounded">
                            <p className="text-sm text-red-600">{error}</p>
                        </div>
                    )}

                    {file && (
                        <div className="p-3 bg-gray-50 rounded border">
                            <p className="text-sm font-medium">{file.name}</p>
                            <p className="text-xs text-gray-600">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                        </div>
                    )}

                    {file && (
                        <button
                            onClick={handleUpload}
                            className="w-full py-2 px-4 bg-blue-600 text-white rounded hover:bg-blue-700"
                        >
                            Upload
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}