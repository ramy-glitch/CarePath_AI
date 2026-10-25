const DB_NAME = "carepath";
const STORE = "files";

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE)) {
        database.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function run(mode, action) {
  return openDatabase().then(
    (database) =>
      new Promise((resolve, reject) => {
        const transaction = database.transaction(STORE, mode);
        const store = transaction.objectStore(STORE);
        const request = action(store);
        transaction.oncomplete = () => {
          database.close();
          resolve(request ? request.result : undefined);
        };
        transaction.onerror = () => {
          database.close();
          reject(transaction.error);
        };
      }),
  );
}

export function putRecord(record) {
  return run("readwrite", (store) => store.put(record));
}

export function getAllRecords() {
  return run("readonly", (store) => store.getAll());
}

export function deleteRecord(id) {
  return run("readwrite", (store) => store.delete(id));
}

export function deleteEveryRecord() {
  return run("readwrite", (store) => store.clear());
}
