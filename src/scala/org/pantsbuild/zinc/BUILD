scala_library(
  name='zinc',
  provides=artifact(
    org='org.pantsbuild',
    name='zinc',
    repo=public,
    publication_metadata=pants_library('The SBT incremental compiler for nailgun')
  ),
  dependencies=[
    '3rdparty/jvm/com/typesafe/sbt:incremental-compiler',
    '3rdparty:guava',
    '3rdparty:jsr305',
    'src/scala/org/pantsbuild/zinc/logging',
  ],
  sources=globs('*.scala'),
)
