import { Attachment, OutgoingAttachment } from '../models/chat.models';

/** Image types Claude can see; other files are sent as documents. */
export const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];

/** Read a file as an attachment: base64 content without the `data:` prefix. */
export function readAttachment(file: File): Promise<OutgoingAttachment> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () =>
      resolve({
        name: file.name,
        media_type: file.type || 'application/octet-stream',
        data: (reader.result as string).split(',')[1] ?? '',
      });
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** How an attachment is displayed: images get a data URL to preview. */
export function toDisplay({ name, media_type, data }: OutgoingAttachment): Attachment {
  const url = media_type.startsWith('image/') ? `data:${media_type};base64,${data}` : undefined;
  return { name, media_type, url };
}
