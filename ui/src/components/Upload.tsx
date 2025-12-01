import { Link } from 'react-router';
import { useUploadStore } from '../store/uploadStore';

const MAX_FILE_SIZE_MB = 3;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

export default function Upload() {
    const { 
        uploadForm, 
        setUploadForm, 
        resetUploadForm, 
        uploadFile 
    } = useUploadStore()

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        
        resetUploadForm();

        if (selectedFile) {
            if (selectedFile.type !== 'application/pdf') {
                setUploadForm({ error: 'Please select a PDF file.' });
                return;
            }

            if (selectedFile.size > MAX_FILE_SIZE_BYTES) {
                setUploadForm({ error: `File size must be less than ${MAX_FILE_SIZE_MB}MB.` });
                return;
            }

            setUploadForm({ selectedFile });
        }
    };

    const handleUpload = async () => {
        if (!uploadForm.selectedFile) return;
        await uploadFile(uploadForm.selectedFile);
        
        // Reset file input
        const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
        if (fileInput) fileInput.value = '';
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

                    {uploadForm.error && (
                        <div className="error-notification">
                            <p className="error-text">{uploadForm.error}</p>
                        </div>
                    )}

                    {uploadForm.uploadResult && (
                        <div className="success-notification">
                            <p className="success-text">File uploaded successfully!</p>
                            <p className="success-detail">ID: {uploadForm.uploadResult.id}</p>
                            <p className="success-detail">Size: {(uploadForm.uploadResult.size / 1024 / 1024).toFixed(2)} MB</p>
                        </div>
                    )}

                    {uploadForm.selectedFile && !uploadForm.error && (
                        <>
                            <div className="file-preview">
                                <p className="file-name">{uploadForm.selectedFile.name}</p>
                                <p className="file-size">{(uploadForm.selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                            </div>
                            <button
                                onClick={handleUpload}
                                disabled={uploadForm.uploading}
                                className={`button-upload ${
                                    uploadForm.uploading 
                                        ? 'button-upload-disabled' 
                                        : 'button-upload-enabled'
                                }`}
                            >
                                {uploadForm.uploading ? 'Uploading...' : 'Upload'}
                            </button>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}