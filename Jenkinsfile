pipeline {
  agent any
  stages {
    stage('build') {
      when {
        anyOf {
          branch 'master'
          branch 'production'
          branch 'release_candidate'
          changeRequest title: ".*JENKINSFILE_TESTING.*", comparator: 'REGEXP'
          buildingTag()
        }
      }
          steps {
            publishWheels codeBuildEnv: '[ { RUN_TESTS, false },{ pip_version, pip3.8 } ]'
          }
        }
    }
}
