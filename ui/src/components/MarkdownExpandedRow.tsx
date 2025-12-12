import ReactMarkdown from 'react-markdown';
import type { Paper } from '../types';

interface MarkdownExpandedRowProps {
  uploadId: string;
  paper: Paper;
}

export default function MarkdownExpandedRow({ uploadId, paper }: MarkdownExpandedRowProps) {
  return (
    <tr key={`${uploadId}-markdown`}>
      <td colSpan={2} className="expanded-content">
        <div className="md-content markdown-content">
          <ReactMarkdown>
            {paper.content}
          </ReactMarkdown>
        </div>
      </td>
    </tr>
  )
}