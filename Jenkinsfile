pipeline {
  agent any
  stages {
    stage('build') {
      when {
        anyOf {
          branch 'master'
          branch 'production'
          branch 'release_candidate'
        }
      }
      parallel {
        stage('build_trusty') {
          steps {
            awsCodeBuild projectName: 'build_trusty_python_library',
                         envVariables: '[ { RUN_TESTS, false }, { CREATE_SDIST, true } ]',
                         region: 'us-east-1',
                         sourceControlType: 'jenkins',
                         credentialsType: 'keys'
          }
        }
        stage('build_bionic') {
          steps {
            awsCodeBuild projectName: 'build_bionic_python_library',
                         envVariables: '[ { RUN_TESTS, false }, { CREATE_SDIST, true } ]',
                         region: 'us-east-1',
                         sourceControlType: 'jenkins',
                         credentialsType: 'keys'
          }
        }
      }
    }
  }
}
