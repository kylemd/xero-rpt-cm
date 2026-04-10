/**
 * Reusable drag-and-drop file input component.
 *
 * Light-theme styling: dashed border, blue on drag, green when file loaded.
 */

import { useCallback, useRef, useState } from 'react';

interface FileDropZoneProps {
  label: string;
  required?: boolean;
  accept: string;
  onFile: (file: File) => void;
  fileName?: string;
  status?: string;
}

export default function FileDropZone({
  label,
  required,
  accept,
  onFile,
  fileName,
  status,
}: FileDropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onFile(file);
    },
    [onFile],
  );

  const handleClick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) onFile(file);
      // Reset so re-selecting same file triggers change
      e.target.value = '';
    },
    [onFile],
  );

  const hasFile = Boolean(fileName);

  const borderClass = isDragging
    ? 'border-blue-500 bg-blue-50'
    : hasFile
      ? 'border-green-500 bg-green-50'
      : 'border-gray-300 hover:border-gray-400';

  return (
    <div className="mb-3">
      <label className="block text-xs font-medium text-gray-600 mb-1">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      <div
        className={`relative border-2 border-dashed rounded-lg p-3 text-center cursor-pointer transition-colors ${borderClass}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleChange}
          className="hidden"
        />
        {hasFile ? (
          <div>
            <p className="text-sm font-medium text-green-700 truncate">
              {fileName}
            </p>
            {status && (
              <p className="text-xs text-green-600 mt-0.5">{status}</p>
            )}
          </div>
        ) : (
          <div>
            <p className="text-sm text-gray-500">
              Drop file here or click to browse
            </p>
            <p className="text-xs text-gray-400 mt-0.5">{accept}</p>
          </div>
        )}
      </div>
    </div>
  );
}
