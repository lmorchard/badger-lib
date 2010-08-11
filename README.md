Dependencies for [badger](http://github.com/lmorchard/badger).

It goes something like this:

    pip install --no-install --build=vendor/packages --src=vendor/src -I -r requirements/dev.txt
    find packages src -type d -depth 1 >| badger.pth

    git init
    for f in src/*; do
        pushd $f >/dev/null && REPO=$(git config remote.origin.url) && popd > /dev/null && git submodule add $REPO $f
        done
    git add .
