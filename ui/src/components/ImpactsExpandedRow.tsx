import type { Impact } from '../types';

interface ImpactsExpandedRowProps {
  uploadId: string;
  impacts: Impact[];
}

export default function ImpactsExpandedRow({ uploadId, impacts }: ImpactsExpandedRowProps) {
  return (
    <tr key={`${uploadId}-impacts`}>
      <td colSpan={2} className="expanded-content">
        <div className="impacts-content">
          <h4 className="impacts-header">
            Extracted Impacts ({impacts.length} found)
          </h4>
          {impacts.length === 0 ? (
            <p className="impacts-empty">No impacts found in this paper.</p>
          ) : (
            <div className="impacts-table-container">
              <table className="impacts-table">
                <thead>
                  <tr className="impacts-table-header">
                    <th className="impacts-table-header-cell">Species</th>
                    <th className="impacts-table-header-cell">Mechanism</th>
                    <th className="impacts-table-header-cell">Category</th>
                    <th className="impacts-table-header-cell">Confidence</th>
                    <th className="impacts-table-header-cell">Impacted Species</th>
                    <th className="impacts-table-header-cell">Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {impacts.map((impact, index) => (
                    <tr key={index} className={index % 2 === 0 ? 'impacts-table-row-even' : 'impacts-table-row-odd'}>
                      <td className="impacts-table-cell impacts-species-cell">
                        {impact.alien_species}
                      </td>
                      <td className="impacts-table-cell">
                        {impact.mechanism}
                      </td>
                      <td className="impacts-table-cell impacts-species-cell">
                        <span className={`impact-category-badge ${
                          impact.category === 'MV' ? 'impact-category-mv' :
                          impact.category === 'MR' ? 'impact-category-mr' :
                          impact.category === 'MO' ? 'impact-category-mo' :
                          impact.category === 'MN' ? 'impact-category-mn' :
                          impact.category === 'MC' ? 'impact-category-mc' :
                          'impact-category-default'
                        }`}>
                          {impact.category}
                        </span>
                      </td>
                      <td className="impacts-table-cell">
                        {impact.confidence || 'N/A'}
                      </td>
                      <td className="impacts-table-cell">
                        {impact.impacted_species.length > 0 
                          ? impact.impacted_species.join(', ') 
                          : 'Not specified'
                        }
                      </td>
                      <td className="impacts-table-cell evidence-cell">
                        <div className="evidence-truncate" title={impact.evidence}>
                          {impact.evidence.length > 100 
                            ? `${impact.evidence.substring(0, 100)}...` 
                            : impact.evidence
                          }
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}