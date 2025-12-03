'use client'

import { useState } from 'react'
import EnhancedAgentProgress from '@/components/EnhancedAgentProgress'
import { MultiAgentResult } from '@/lib/api'
import styles from './page.module.css'

export default function Home() {
  const [query, setQuery] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [results, setResults] = useState<MultiAgentResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || isAnalyzing) return

    setIsAnalyzing(true)
    setError(null)
    setResults(null)
  }

  const handleComplete = (result: MultiAgentResult) => {
    setResults(result)
    setIsAnalyzing(false)
  }

  const handleError = (errorMessage: string) => {
    setError(errorMessage)
    setIsAnalyzing(false)
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1>🔬 FDA Multi-Agent Intelligence System</h1>
        <p>Harness the power of specialized AI agents to analyze medical device data</p>
      </header>

      <form onSubmit={handleSubmit} className={styles.searchForm}>
        <div className={styles.searchContainer}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter a device name, manufacturer, or safety concern..."
            className={styles.searchInput}
            disabled={isAnalyzing}
          />
          <button 
            type="submit" 
            className={styles.searchButton} 
            disabled={!query.trim() || isAnalyzing}
          >
            <span className={styles.buttonIcon}>{isAnalyzing ? '⏳' : '🔍'}</span>
            {isAnalyzing ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>
        
        <div className={styles.examples}>
          <span>Try:</span>
          <button type="button" onClick={() => setQuery('3M masks')} className={styles.exampleButton}>
            3M masks
          </button>
          <button type="button" onClick={() => setQuery('insulin pumps')} className={styles.exampleButton}>
            insulin pumps
          </button>
          <button type="button" onClick={() => setQuery('Medtronic pacemakers')} className={styles.exampleButton}>
            Medtronic pacemakers
          </button>
        </div>
      </form>

      {error && (
        <div className={styles.error}>
          <span className={styles.errorIcon}>⚠️</span>
          {error}
        </div>
      )}

      {(isAnalyzing || results) && (
        <section className={styles.analysisSection}>
          {isAnalyzing && (
            <EnhancedAgentProgress
              query={query}
              isActive={isAnalyzing}
              onComplete={handleComplete}
              onError={handleError}
            />
          )}

          {results && !isAnalyzing && (
            <div className={styles.results}>
              <h2>✨ Analysis Complete</h2>
              
              <div className={styles.intentCard}>
                <h3>📊 Query Understanding</h3>
                <p><strong>Intent:</strong> {results.intent.primary_intent}</p>
                {results.intent.device_names.length > 0 && (
                  <p><strong>Devices:</strong> {results.intent.device_names.join(', ')}</p>
                )}
                {results.intent.specific_concerns.length > 0 && (
                  <p><strong>Concerns:</strong> {results.intent.specific_concerns.join(', ')}</p>
                )}
                <p><strong>Agents Activated:</strong> {results.intent.required_agents.length}</p>
              </div>

              <div className={styles.agentResults}>
                {Object.entries(results.agent_results).map(([agentName, agentData]) => {
                  const data = agentData[0]
                  if (!data || !data.key_findings) return null

                  const agentIcons: Record<string, string> = {
                    events_specialist: '⚠️',
                    recalls_specialist: '🔄',
                    clearances_specialist: '✅',
                    udi_specialist: '🏷️',
                    classifications_specialist: '📊',
                    pma_specialist: '🔬'
                  }

                  return (
                    <div key={agentName} className={styles.agentCard}>
                      <h3>
                        <span className={styles.agentIcon}>{agentIcons[agentName] || '🤖'}</span>
                        {agentName.replace('_specialist', '').replace('_', ' ').toUpperCase()} SPECIALIST
                      </h3>
                      
                      <div className={styles.dataPoints}>
                        {data.data_points ? `${data.data_points.toLocaleString()} records analyzed` : 'Analysis complete'}
                      </div>

                      <div className={styles.findings}>
                        <h4>Key Findings</h4>
                        {Array.isArray(data.key_findings) ? (
                          <ul>
                            {data.key_findings.slice(0, 5).map((finding: any, i: number) => (
                              <li key={i}>
                                {typeof finding === 'string' ? finding : finding.finding || JSON.stringify(finding)}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className={styles.structuredFindings}>
                            {Object.entries(data.key_findings).map(([key, value]) => (
                              <div key={key} className={styles.finding}>
                                <strong>{key}:</strong>
                                <p>{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {data.recommendations && data.recommendations.length > 0 && (
                        <div className={styles.recommendations}>
                          <h4>Recommendations</h4>
                          <ul>
                            {data.recommendations.slice(0, 3).map((rec: string, i: number) => (
                              <li key={i}>{rec}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              <div className={styles.timestamp}>
                Analysis completed at: {new Date(results.timestamp).toLocaleString()}
              </div>
            </div>
          )}
        </section>
      )}

      <footer className={styles.footer}>
        <p>
          This system uses specialized AI agents to analyze FDA data. Results should be verified 
          with official FDA sources.
        </p>
      </footer>
    </div>
  )
}