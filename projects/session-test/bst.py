"""A binary search tree (BST) supporting insert and search.

Design notes
------------
* Nodes are stored as linked objects (``Node``) rather than parallel arrays, which
  keeps the code readable and maps directly to the textbook algorithm.
* ``insert`` and ``search`` are **iterative**. A recursive version is easier to
  read but blows the Python recursion limit on a badly skewed tree (e.g.
  inserting 100_000 sorted values would raise ``RecursionError``).
* The tree is generic over the key type. Keys only need to support the
  comparison operators they actually use -- ``__lt__`` for insertion and
  ``__eq__`` for lookup.
* Duplicate keys are rejected rather than silently dropped, which keeps the
  invariant "one node per distinct key" true and makes ``insert``'s return
  value meaningful.
"""

from __future__ import annotations

from typing import Generic, Iterator, Optional, TypeVar, Union

K = TypeVar("K")
V = TypeVar("V")

NodeKey = Union[K, "Node[K, V]"]


class Node(Generic[K, V]):
    """A single node in the :class:`BinarySearchTree`.

    A ``Node`` with no children is a leaf; the root of an empty tree is
    represented by ``None`` rather than an empty node, so ``is_empty`` checks
    never have to special-case a node with a missing value.
    """

    __slots__ = ("key", "value", "left", "right")

    def __init__(self, key: K, value: Optional[V] = None) -> None:
        self.key = key
        self.value = value
        self.left: Optional[Node[K, V]] = None
        self.right: Optional[Node[K, V]] = None

    def __repr__(self) -> str:
        return f"Node(key={self.key!r}, value={self.value!r})"


class BinarySearchTree(Generic[K, V]):
    """Binary search tree keyed on ``K``.

    Ordering invariant, held for every node ``n``:

        * every key in ``n.left`` is ``< n.key``
        * every key in ``n.right`` is ``> n.key``
    """

    __slots__ = ("_root", "_size")

    def __init__(self) -> None:
        self._root: Optional[Node[K, V]] = None
        self._size = 0

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        """Number of nodes in the tree."""
        return self._size

    @property
    def root(self) -> Optional[Node[K, V]]:
        """The root node, or ``None`` if the tree is empty."""
        return self._root

    def is_empty(self) -> bool:
        return self._root is None

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------
    def insert(self, key: K, value: Optional[V] = None) -> bool:
        """Insert ``key``/``value`` into the tree.

        Returns ``True`` if a new node was created, ``False`` if the key was
        already present (in which case the tree is left untouched -- the
        existing value is *not* overwritten; use :meth:`put` to upsert).
        """
        if self._root is None:
            self._root = Node(key, value)
            self._size = 1
            return True

        current = self._root
        while True:
            if key == current.key:
                return False  # duplicate: reject
            elif key < current.key:
                if current.left is None:
                    current.left = Node(key, value)
                    self._size += 1
                    return True
                current = current.left
            else:  # key > current.key
                if current.right is None:
                    current.right = Node(key, value)
                    self._size += 1
                    return True
                current = current.right

    def search(self, key: K) -> Optional[Node[K, V]]:
        """Return the node holding ``key``, or ``None`` if it is absent.

        The returned node exposes ``.key`` and ``.value`` and can be used to
        walk to its children.
        """
        current = self._root
        while current is not None:
            if key == current.key:
                return current
            current = current.left if key < current.key else current.right
        return None

    def contains(self, key: K) -> bool:
        """``True`` if ``key`` is present. Thin wrapper over :meth:`search`."""
        return self.search(key) is not None

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """Return the value stored under ``key``, or ``default``."""
        node = self.search(key)
        return default if node is None else node.value

    def put(self, key: K, value: V) -> None:
        """Insert ``key`` or, if present, update its value in place."""
        node = self.search(key)
        if node is None:
            self.insert(key, value)
        else:
            node.value = value

    # ------------------------------------------------------------------
    # Traversal helpers
    # ------------------------------------------------------------------
    def inorder(self) -> Iterator[K]:
        """Yield keys in ascending order using an explicit stack.

        Iterative so that a degenerate (fully skewed) tree does not overflow
        the recursion limit.
        """
        stack: list[Node[K, V]] = []
        current = self._root
        while stack or current is not None:
            while current is not None:
                stack.append(current)
                current = current.left
            current = stack.pop()
            yield current.key
            current = current.right

    def preorder(self) -> Iterator[K]:
        """Yield keys in root-left-right order."""
        stack: list[Node[K, V]] = []
        current = self._root
        while stack or current is not None:
            while current is not None:
                yield current.key
                stack.append(current)
                current = current.left
            current = stack.pop()
            current = current.right

    def __contains__(self, key: object) -> bool:
        """Enables ``key in tree`` syntax."""
        return self.contains(key)  # type: ignore[arg-type]

    def __iter__(self) -> Iterator[K]:
        """Iterating a tree yields its keys in sorted order."""
        return self.inorder()

    def __repr__(self) -> str:
        return f"<BinarySearchTree size={self._size} root={self._root!r}>"
