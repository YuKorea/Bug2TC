pipeline {
  agent any
  stages {
    stage('Setup') {
      steps {
        sh 'rm -rf .venv-ci reports'
        sh 'python3 -m venv .venv-ci'
        sh '. .venv-ci/bin/activate && pip install -r requirements-dev.txt'
      }
    }
    stage('Test') {
      steps {
        sh '. .venv-ci/bin/activate && pytest -v --junitxml=reports/junit.xml --cov=ai_client --cov=bug_report_generator --cov=excel_writer --cov=yona_client --cov=paths --cov-report=term --cov-report=html:reports/htmlcov'
      }
    }
  }
    post {
    always {
      junit allowEmptyResults: true, testResults: 'reports/junit.xml'
      archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
    }
    failure {
      withCredentials([string(credentialsId: 'discord-webhook-url', variable: 'DISCORD_URL')]) {
        sh '''curl -sS -o /dev/null -w "Discord HTTP %{http_code}\\n" -H "Content-Type: application/json" -d "{\\"content\\": \\"Build FAILED: ${JOB_NAME} #${BUILD_NUMBER} ${BUILD_URL}\\"}" "$DISCORD_URL" || echo "notification failed"'''
      }
    }
  }
}