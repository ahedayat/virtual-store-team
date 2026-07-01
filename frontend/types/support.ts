export type Customer = {
  id: number;
  name: string;
  username: string;
  avatar: string;
  lastMsg: string;
  time: string;
  unread: number;
};

export type Message = {
  id: number;
  sender: 'customer' | 'admin';
  text: string;
  time: string;
};
