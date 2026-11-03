pipeline {
  agent any
  stages {
    stage('Setup') {
      steps {
        sh 'python3 -m venv .venv-ci'
        sh '. .venv-ci/bin/activate && pip install -r requirements.txt pytest'
      }
    }
    stage('Test') {
      steps {
        sh '. .venv-ci/bin/activate && pytest -v --junitxml=reports/junit.xml'
      }
    }
  }
  post {
    always {
      junit allowEmptyResults: true, testResults: 'reports/junit.xml'
    }
  }
}