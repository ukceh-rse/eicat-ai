import React, { useState, useEffect } from 'react';
import { FaSearch, FaSpinner, FaPlus, FaMinus, FaTimes } from 'react-icons/fa';
import type { SpeciesNames } from '../types';
import { API_ENDPOINTS } from '../config/api';

interface SpeciesSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSpeciesSelected: (species: SpeciesNames) => void;
  currentSpecies?: SpeciesNames | null;
}

export default function SpeciesSearchModal({ 
  isOpen, 
  onClose, 
  onSpeciesSelected, 
  currentSpecies 
}: SpeciesSearchModalProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState<SpeciesNames[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSpecies, setSelectedSpecies] = useState<SpeciesNames | null>(currentSpecies || null);
  const [editingScientificName, setEditingScientificName] = useState('');
  const [editingVernacularNames, setEditingVernacularNames] = useState<string[]>([]);

  // Initialize editing state when species is selected
  useEffect(() => {
    if (selectedSpecies) {
      setEditingScientificName(selectedSpecies.scientific_name);
      setEditingVernacularNames([...selectedSpecies.vernacular_names]);
    }
  }, [selectedSpecies]);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setSearchTerm('');
      setSearchResults([]);
      setError(null);
      setSelectedSpecies(currentSpecies || null);
      if (currentSpecies) {
        setEditingScientificName(currentSpecies.scientific_name);
        setEditingVernacularNames([...currentSpecies.vernacular_names]);
      }
    }
  }, [isOpen, currentSpecies]);

  const handleSearch = async () => {
    if (!searchTerm.trim()) return;

    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(API_ENDPOINTS.gbifSearch(searchTerm));
      if (!response.ok) {
        throw new Error('Failed to search GBIF database');
      }
      
      const results: SpeciesNames[] = await response.json();
      setSearchResults(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const handleSpeciesSelect = (species: SpeciesNames) => {
    setSelectedSpecies(species);
    setEditingScientificName(species.scientific_name);
    setEditingVernacularNames([...species.vernacular_names]);
  };

  const handleAddVernacularName = () => {
    setEditingVernacularNames([...editingVernacularNames, '']);
  };

  const handleRemoveVernacularName = (index: number) => {
    setEditingVernacularNames(editingVernacularNames.filter((_, i) => i !== index));
  };

  const handleVernacularNameChange = (index: number, value: string) => {
    const updated = [...editingVernacularNames];
    updated[index] = value;
    setEditingVernacularNames(updated);
  };

  const handleConfirm = () => {
    if (!editingScientificName.trim()) {
      setError('Scientific name is required');
      return;
    }

    const finalSpecies: SpeciesNames = {
      scientific_name: editingScientificName.trim(),
      vernacular_names: editingVernacularNames.filter(name => name.trim() !== '')
    };

    onSpeciesSelected(finalSpecies);
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content species-search-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Select Species for Analysis</h3>
          <button className="modal-close" onClick={onClose}>
            <FaTimes />
          </button>
        </div>

        <div className="modal-body">
          {/* Search Section */}
          <div className="search-section">
            <h4>Search GBIF Database</h4>
            <div className="search-input-group">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Enter species name..."
                className="search-input"
              />
              <button 
                onClick={handleSearch} 
                disabled={loading || !searchTerm.trim()}
                className="search-button"
              >
                {loading ? <FaSpinner className="spinner" /> : <FaSearch />}
              </button>
            </div>

            {error && (
              <div className="error-message">{error}</div>
            )}

            {/* Search Results */}
            {searchResults.length > 0 && (
              <div className="search-results">
                <h5>Search Results</h5>
                <div className="species-list">
                  {searchResults.map((species, index) => (
                    <div 
                      key={index}
                      className={`species-item ${selectedSpecies?.scientific_name === species.scientific_name ? 'selected' : ''}`}
                      onClick={() => handleSpeciesSelect(species)}
                    >
                      <div className="scientific-name">{species.scientific_name}</div>
                      {species.vernacular_names.length > 0 && (
                        <div className="vernacular-names">
                          {species.vernacular_names.join(', ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Selected Species Editing Section */}
          {selectedSpecies && (
            <div className="editing-section">
              <h4>Edit Selected Species</h4>
              
              <div className="form-group">
                <label htmlFor="scientific-name">Scientific Name *</label>
                <input
                  id="scientific-name"
                  type="text"
                  value={editingScientificName}
                  onChange={(e) => setEditingScientificName(e.target.value)}
                  className="form-input"
                  placeholder="Enter scientific name..."
                />
              </div>

              <div className="form-group">
                <label>Vernacular Names</label>
                {editingVernacularNames.map((name, index) => (
                  <div key={index} className="vernacular-name-input">
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => handleVernacularNameChange(index, e.target.value)}
                      className="form-input"
                      placeholder="Enter common name..."
                    />
                    <button 
                      onClick={() => handleRemoveVernacularName(index)}
                      className="remove-button"
                      type="button"
                    >
                      <FaMinus />
                    </button>
                  </div>
                ))}
                <button 
                  onClick={handleAddVernacularName}
                  className="add-button"
                  type="button"
                >
                  <FaPlus /> Add Vernacular Name
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button onClick={onClose} className="button-secondary">
            Cancel
          </button>
          <button 
            onClick={handleConfirm} 
            disabled={!selectedSpecies || !editingScientificName.trim()}
            className="button-primary"
          >
            Use This Species
          </button>
        </div>
      </div>
    </div>
  );
}